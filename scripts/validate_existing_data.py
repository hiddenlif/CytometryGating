"""Offline development checks on existing FCS files and author workspaces.

Replay and invariance checks use FlowKit throughout; they do not establish
agreement with FlowJo or biological accuracy. No data are downloaded.
"""
import argparse
import copy
import hashlib
import importlib.metadata
import io
import json
from collections import Counter
from pathlib import Path

import flowkit as fk
import numpy as np

from fetch_public_data import checksum
from inspect_fcs import inspect_file

ROOT = Path(__file__).resolve().parents[1]


def verify_source(row):
    path = ROOT / row['path']
    if path.stat().st_size != row['bytes'] or checksum(path, row['checksum_algorithm']) != row['checksum']:
        raise ValueError(f"Source integrity failed: {row['path']}")
    return path


def assert_membership(expected, actual, parent):
    arrays = [np.asarray(v) for v in (expected, actual, parent)]
    if any(a.ndim != 1 or a.dtype != np.bool_ for a in arrays):
        raise ValueError('Membership must be a one-dimensional boolean array')
    if len({len(a) for a in arrays}) != 1:
        raise ValueError('Membership event counts differ')
    if np.any(arrays[0] & ~arrays[2]):
        raise ValueError('Child membership escapes its parent')
    mismatches = int(np.count_nonzero(arrays[0] != arrays[1]))
    if mismatches:
        raise ValueError(f'{mismatches} event membership mismatches')


def exact_index(rows):
    indexed = {}
    for row in rows:
        if row['filename'] in indexed:
            raise ValueError('Ambiguous duplicate filename in sample mapping')
        indexed[row['filename']] = row
    return indexed


def sample_from_events(sample, indices):
    # Preserve channel identity and acquisition scaling for these FCS samples.
    # FlowKit's raw events already include FCS acquisition scaling; ndarray
    # construction must not apply it a second time.
    return fk.Sample(sample.get_events(source='raw')[indices], sample_id=sample.id,
                     channel_labels=sample.pnn_labels, preprocess=False)


def check_workspace(row, index, output):
    path = verify_source(row)
    structure = fk.Workspace(str(path), load_missing_file_data=True)
    ids = structure.get_sample_ids(loaded_only=False)
    missing = [sid for sid in ids if sid not in index or not (ROOT / index[sid]['path']).exists()]
    samples = [fk.Sample(str(verify_source(index[sid])), sample_id=sid, preprocess=False)
               for sid in ids if sid not in missing]
    workspace = fk.Workspace(str(path), fcs_samples=samples, load_missing_file_data=True)
    workspace.analyze_samples(use_mp=False)
    cases = []
    for sid in workspace.get_sample_ids():
        sample = workspace.get_sample(sid)
        strategy = workspace.get_gating_strategy(sid)
        direct = strategy.gate_sample(sample)
        order = np.random.default_rng(20261018).permutation(sample.event_count)
        permuted = strategy.gate_sample(sample_from_events(sample, order))
        subset_indices = order[:max(1, sample.event_count // 2)]
        subset = strategy.gate_sample(sample_from_events(sample, subset_indices))
        uncompensated = copy.deepcopy(strategy)
        for name, gate_path in uncompensated.get_gate_ids():
            for dimension in uncompensated.get_gate(name, gate_path, sample_id=sid).dimensions:
                dimension.compensation_ref = 'uncompensated'
        ablated = uncompensated.gate_sample(sample)
        gates, masks = [], {}
        for gate_no, (name, gate_path) in enumerate(strategy.get_gate_ids()):
            expected = workspace.get_gate_membership(sid, name, gate_path)
            parent = (np.ones(sample.event_count, dtype=bool) if gate_path == ('root',)
                      else workspace.get_gate_membership(sid, gate_path[-1], gate_path[:-1]))
            assert_membership(expected, direct.get_gate_membership(name, gate_path), parent)
            assert_membership(expected[order], permuted.get_gate_membership(name, gate_path), parent[order])
            assert_membership(expected[subset_indices], subset.get_gate_membership(name, gate_path), parent[subset_indices])
            count, denominator = int(expected.sum()), int(parent.sum())
            relative = 100 * count / denominator if denominator else None
            reported = direct.get_gate_relative_percent(name, gate_path)
            if relative is not None and not np.isclose(relative, reported, rtol=0, atol=1e-10):
                raise ValueError('Reported relative percent disagrees with parent membership')
            gates.append({'gate': name, 'path': list(gate_path), 'count': count,
                          'parent_count': denominator, 'percent_of_parent': relative,
                          'percent_of_all_events': 100 * count / sample.event_count,
                          'compensation_omission_membership_changes': int(np.count_nonzero(
                              expected != ablated.get_gate_membership(name, gate_path)))})
            masks[f'gate_{gate_no}'] = expected
        prefix = hashlib.sha256((row['filename'] + sid).encode()).hexdigest()[:16]
        np.savez_compressed(output / f'{prefix}-membership.npz', **masks)
        buffer = io.BytesIO()
        fk.export_gatingml(strategy, buffer, sample_id=sid)
        xml = buffer.getvalue()
        try:
            reloaded = fk.parse_gating_xml(io.BytesIO(xml))
        except (ValueError, NotImplementedError) as exc:
            export_status, export_error = 'blocked', f'{type(exc).__name__}: {exc}'
            # Invalid export stays local and is explicitly labeled for diagnosis.
            (output / f'{prefix}-INVALID-export.xml').write_bytes(xml)
        else:
            if set(strategy.get_gate_ids()) != set(reloaded.get_gate_ids()):
                raise ValueError('GatingML changed gate identities or hierarchy')
            replay = reloaded.gate_sample(sample)
            for name, gate_path in strategy.get_gate_ids():
                expected = workspace.get_gate_membership(sid, name, gate_path)
                assert_membership(expected, replay.get_gate_membership(name, gate_path), np.ones(sample.event_count, dtype=bool))
            export_status, export_error = 'passed', None
            (output / f'{prefix}-gates.xml').write_bytes(xml)
        cases.append({'sample': sid, 'source_path': index[sid]['path'], 'events': sample.event_count,
                      'membership_file': f'{prefix}-membership.npz', 'gates': gates,
                      'direct_replay': 'passed', 'event_permutation': 'passed', 'event_subset': 'passed',
                      'parent_denominators': 'passed', 'gatingml_roundtrip': export_status,
                      'gatingml_error': export_error,
                      'transformation_types': dict(Counter(type(t).__name__ for t in strategy.transformations.values()))})
    return {'workspace': row['filename'], 'source_checksum': row['checksum'],
            'missing_exact_sample_references': missing, 'cases': cases}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'reports/local/testing')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((ROOT / 'data/manifests/public-files.json').read_text())
    inventory, missing = [], []
    for row in manifest['files']:
        if not row['filename'].lower().endswith('.fcs'):
            continue
        if not (ROOT / row['path']).exists():
            missing.append(row['path'])
            continue
        path = verify_source(row)
        inspected = inspect_file(path)
        if inspected['nonfinite_values']:
            raise ValueError(f'Nonfinite events in {row["path"]}')
        inventory.append({'dataset': row['dataset'], 'filename': row['filename'], 'role': row['role'],
                          'source_checksum': row['checksum'], **inspected})
    nk = [r for r in manifest['files'] if r['dataset'] == 'car-nk-knockin']
    index = exact_index([r for r in nk if r['filename'].lower().endswith('.fcs')])
    workspaces = []
    missing_workspaces = []
    for row in nk:
        if not row['filename'].lower().endswith('.wsp'):
            continue
        if not (ROOT / row['path']).exists():
            missing_workspaces.append(row['filename'])
            continue
        workspaces.append(check_workspace(row, index, args.output))
    cases = [c for w in workspaces for c in w['cases']]
    if not inventory or not cases:
        raise ValueError('Available FCS files and matched workspace cases are required')
    summary = {
        'flowkit_version': importlib.metadata.version('flowkit'),
        'scope': 'offline development data; no new downloads',
        'fcs_checksum_and_parse_passed': len(inventory), 'events_reparsed': sum(r['events'] for r in inventory),
        'by_dataset': dict(Counter(r['dataset'] for r in inventory)),
        'not_downloaded_fcs': len(missing), 'workspaces_replayed': len(workspaces),
        'workspace_sample_cases': len(cases), 'gate_cases': sum(len(c['gates']) for c in cases),
        'direct_permutation_subset_and_parent_checks': 'passed',
        'gatingml_roundtrip_passed': sum(c['gatingml_roundtrip'] == 'passed' for c in cases),
        'gatingml_roundtrip_blocked': sum(c['gatingml_roundtrip'] == 'blocked' for c in cases),
        'samples_affected_by_compensation_omission': sum(any(g['compensation_omission_membership_changes'] for g in c['gates']) for c in cases),
        'missing_exact_workspace_sample_references': sum(len(w['missing_exact_sample_references']) for w in workspaces),
        'missing_workspaces': missing_workspaces,
        'limitations': ['Replay and invariance use the same FlowKit engine, not independent FlowJo agreement.',
                       'Authors supplied fixed gates; automatic gate fitting and biological accuracy are not tested.',
                       'FCS metadata and workspace filename matching do not establish donor independence.',
                       'Unavailable files and unmatched references are excluded, never substituted.'],
    }
    (args.output / 'validation.json').write_text(json.dumps({'summary': summary, 'inventory': inventory,
        'missing_fcs': missing, 'workspaces': workspaces}, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
