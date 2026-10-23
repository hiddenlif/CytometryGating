"""Build the complete existing-data scatterplot review and GitHub report.

Plots include every event. Workspace plotting uses the exact preprocessing
routine used by pinned FlowKit 1.3.2 and verifies geometry against membership.
No gate, compensation matrix, or biological label is fitted by this script.
"""
import csv
import hashlib
import html
import json
import math
import re
from collections import Counter
from pathlib import Path

import flowkit as fk
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from matplotlib.patches import Polygon, Rectangle
import numpy as np
from markdown_it import MarkdownIt

from validate_existing_data import ROOT, exact_index, verify_source

ASSETS = ROOT / 'docs/assets/testing'


def density_scatter(ax, x, y):
    """One point per event; color is the number of events in its 2-D bin."""
    counts, xe, ye = np.histogram2d(x, y, bins=100)
    ix = np.clip(np.searchsorted(xe, x, side='right') - 1, 0, 99)
    iy = np.clip(np.searchsorted(ye, y, side='right') - 1, 0, 99)
    z = counts[ix, iy]
    order = np.argsort(z, kind='stable')
    ax.scatter(x[order], y[order], c=z[order], s=3, linewidths=0,
               cmap='viridis', norm=LogNorm(vmin=1, vmax=max(2, z.max())), rasterized=True)
    ax.grid(alpha=.12)
    ax.tick_params(labelsize=9)


def annotate_bounds(ax, gate, color='#e83e8c', linestyle='-'):
    if isinstance(gate, fk.gates.PolygonGate):
        ax.add_patch(Polygon(gate.vertices, closed=True, fill=False, edgecolor=color, linewidth=2, linestyle=linestyle))
    elif isinstance(gate, fk.gates.RectangleGate):
        xd, yd = gate.dimensions
        if all(v is not None for v in [xd.min, xd.max, yd.min, yd.max]):
            ax.add_patch(Rectangle((xd.min, yd.min), xd.max-xd.min, yd.max-yd.min,
                                   fill=False, edgecolor=color, linewidth=2, linestyle=linestyle))
        else:
            for v in [xd.min, xd.max]:
                if v is not None:
                    ax.axvline(v, color=color, linewidth=2, linestyle=linestyle)
            for v in [yd.min, yd.max]:
                if v is not None:
                    ax.axhline(v, color=color, linewidth=2, linestyle=linestyle)
    else:
        raise ValueError(f'Unsupported gate geometry {type(gate).__name__}')
    ax.autoscale_view()


def dimension_label(dimension, strategy):
    transform = strategy.transformations.get(dimension.transformation_ref)
    label = type(transform).__name__.replace('Transform', '') if transform else 'raw'
    comp = 'compensated; ' if dimension.compensation_ref not in [None, 'uncompensated'] else ''
    return f'{dimension.id}\n[{comp}{label} coordinates]'


def workspace_plot(workspace, sample_id, output, heading='Author workspace gates', original_strategy=None):
    sample = workspace.get_sample(sample_id)
    strategy = workspace.get_gating_strategy(sample_id)
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    records = []
    gate_ids = strategy.get_gate_ids()
    if len(gate_ids) != 4:
        raise ValueError('Expected the four-stage author hierarchy')
    for ax, (name, path) in zip(axes.flat, gate_ids):
        gate = strategy.get_gate(name, path, sample_id=sample_id)
        if len(gate.dimensions) != 2:
            raise ValueError('A scatterplot requires two gate dimensions')
        # This is the same pinned method used by FlowKit's own plot_gate().
        coordinates = strategy._preprocess_sample_events(sample, gate)
        parent = (np.ones(sample.event_count, dtype=bool) if path == ('root',)
                  else workspace.get_gate_membership(sample_id, path[-1], path[:-1]))
        member = workspace.get_gate_membership(sample_id, name, path)
        geometric_members = np.asarray(gate.apply(coordinates), dtype=bool) & parent
        if not np.array_equal(geometric_members, member):
            raise ValueError('Plotted geometry does not reproduce recorded membership')
        x = coordinates[gate.dimensions[0].id].to_numpy()[parent]
        y = coordinates[gate.dimensions[1].id].to_numpy()[parent]
        density_scatter(ax, x, y)
        revised = original_strategy is not None and name in ['No Debris', 'Singlets']
        if revised:
            annotate_bounds(ax, original_strategy.get_gate(name, path, sample_id=sample_id), color='#777777', linestyle='--')
        annotate_bounds(ax, gate, color='#ed8a00' if revised else '#e83e8c')
        if revised and name=='Singlets':
            vertices=np.asarray(gate.vertices)
            ax.scatter(vertices[:,0],vertices[:,1],s=40,color='#1879c9',edgecolors='white',linewidths=.8,zorder=5)
        ax.set_xlabel(dimension_label(gate.dimensions[0], strategy), fontsize=10)
        ax.set_ylabel(dimension_label(gate.dimensions[1], strategy), fontsize=10)
        count, denominator = int(member.sum()), int(parent.sum())
        percent = 100*count/denominator if denominator else None
        ax.set_title(f'{name}: {count:,} / {denominator:,} ({percent:.2f}% of parent)', fontsize=12)
        records.append({'gate': name, 'parent': path[-1], 'count': count, 'parent_count': denominator,
                        'percent_of_parent': percent, 'events_plotted': len(x),
                        'dimensions': [vars(d) for d in gate.dimensions], 'geometry_membership_verified': True})
    fig.suptitle(f'{sample_id}\n{heading}; all parent events shown', fontsize=15)
    note = ('Orange: user-guided revision | Blue: digitized vertices | Dashed gray: original | Pink: unchanged live/CAR geometry'
            if original_strategy is not None else 'Pink: author gate boundary | Color: local event density | Fractions use full event counts, not sampled displays')
    fig.text(.5, .012, note,
             ha='center', fontsize=10)
    fig.tight_layout(rect=(0, .04, 1, .94))
    fig.savefig(output, dpi=145)
    plt.close(fig)
    return records


def raw_plot(row, sample, fitted, output):
    events = sample.get_events(source='raw')
    fsc = events[:, sample.get_channel_index('FSC-A')]
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.7))
    selected = None
    if fitted:
        config = fitted['gate']
        if hashlib.md5((ROOT/row['path']).read_bytes()).hexdigest() != config['input_md5']:
            raise ValueError('Fitted gate source differs from plotted FCS')
        selected = fsc >= config['lower_bound']
        if config['upper_bound'] is not None:
            selected &= fsc < config['upper_bound']
        expected = np.loadtxt(ROOT/fitted['output']/'r-membership.csv', delimiter=',', skiprows=1, dtype=int)
        if not np.array_equal(expected[:, 0], np.arange(sample.event_count)) or not np.array_equal(selected, expected[:, 1].astype(bool)):
            raise ValueError('Displayed FSC boundary differs from openCyto membership')
    for ax, y_name in zip(axes, ['SSC-A', 'FSC-H']):
        y = events[:, sample.get_channel_index(y_name)]
        density_scatter(ax, fsc, y)
        if fitted:
            ax.axvline(fitted['gate']['lower_bound'], color='#e83e8c', linewidth=2, label='openCyto FSC threshold')
            ax.legend(loc='upper right', fontsize=8)
        ax.set_xlabel('FSC-A [raw acquisition-scaled coordinates]')
        ax.set_ylabel(f'{y_name} [raw acquisition-scaled coordinates]')
    title = f"{row['filename']} | {sample.event_count:,} events"
    note = 'Raw scatter review; no biological gates or fluorescence compensation applied'
    if fitted:
        title += f'\nAbove FSC threshold: {selected.sum():,} / {sample.event_count:,} ({100*selected.mean():.2f}%)'
        note = 'Engineering-only FSC gate; selected region is to the right of the pink line; no cell identity assigned'
    fig.suptitle(title, fontsize=12)
    fig.text(.5, .025, note, ha='center', fontsize=10)
    fig.tight_layout(rect=(0, .06, 1, .90))
    fig.savefig(output, dpi=135)
    plt.close(fig)
    return int(selected.sum()) if selected is not None else None


def contact_sheet(records, destination):
    fig, axes = plt.subplots(math.ceil(len(records)/3), 3, figsize=(16, 3.1*math.ceil(len(records)/3)), squeeze=False)
    for ax in axes.flat:
        ax.axis('off')
    for ax, r in zip(axes.flat, records):
        ax.imshow(plt.imread(ASSETS/r['image']))
        ax.set_title(r['filename'], fontsize=7, wrap=True)
    fig.tight_layout()
    fig.savefig(destination, dpi=155)
    plt.close(fig)


def write_csv(path, records, fields):
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fields, extrasaction='ignore', lineterminator='\n')
        writer.writeheader()
        writer.writerows(records)


def register_reviews(receipt):
    path=ASSETS/'reviews/nk-her2-v1/results.json'
    if path.exists():
        review=json.loads(path.read_text())
        if hashlib.sha256((ROOT/review['configuration']).read_bytes()).hexdigest()!=review['configuration_sha256']:
            raise ValueError('Review configuration changed; rerun apply_review_guidance.py')
        receipt['review_variants']=[{'id':review['id'],'sample':review['sample'],
                                    'results':'reviews/nk-her2-v1/results.json','source_files_added':0}]
        for filename,digest in review['figure_sha256'].items():
            if hashlib.sha256((path.parent/filename).read_bytes()).hexdigest()!=digest:
                raise ValueError('Reviewed figure or guidance image changed')
            receipt['figure_sha256']['reviews/nk-her2-v1/'+filename]=digest


def review_section():
    path=ASSETS/'reviews/nk-her2-v1/results.json'
    if not path.exists():
        return []
    review=json.loads(path.read_text())
    stages={g['gate']:g for g in review['gates']}
    root='assets/testing/reviews/nk-her2-v1/'
    lines=['## User-guided revision: NK HER2 v1',
           '**Latest reviewed example: `NK Cells_Her2_CAR.fcs`.** The first two gates now follow the user’s orange line and singlet polygon. The diagonal excludes the low-FSC cluster on its left; its retained side is intersected with the original outer scatter gate. The tighter singlet gate is applied to that revised parent.',
           'The boundaries were **approximately digitized from the supplied image**, using its axis ticks and eight blue vertex centers. This is a manual, sample-specific development revision, not an automatic fit or an exact vector annotation. Original author gates are retained below; these fixed coordinates have not been applied to other files.',
           '| Gate | Original count / parent | Revised count / parent | Revised % of parent | Removed vs original | Added vs original |',
           '|---|---:|---:|---:|---:|---:|']
    for g in review['gates']:
        lines.append(f"| {g['gate']} | {g['original_count']:,} / {g['original_parent_count']:,} | {g['revised_count']:,} / {g['revised_parent_count']:,} | {g['revised_percent_of_parent']:.2f}% | {g['excluded_vs_original']:,} | {g['included_vs_original']:,} |")
    lines += [f"The revised first gate excludes **{stages['No Debris']['excluded_vs_original']:,} additional events** relative to the author gate. The drawn singlet boundary also extends beyond part of the original polygon, so it adds {stages['Singlets']['included_vs_original']:,} previously excluded events while removing {stages['Singlets']['excluded_vs_original']:,}. Downstream membership is recalculated; it is not obtained by simply subtracting counts.",
              f"**Live and CAR gate shapes, compensation, and transformations are unchanged.** Their parent populations and denominators have been recomputed. Live/singlet is now {stages['Live']['revised_percent_of_parent']:.2f}%; CAR/live is {stages['CAR']['revised_percent_of_parent']:.2f}%. These are descriptive fractions for this revision.",
              '![User-guided revised scatter, singlet, live, and CAR gates]('+root+'revised-hierarchy.png)',
              '<details>','<summary>Compare the original and revised first two gates</summary>','',
              '![Original author gates compared with the user-guided revision]('+root+'before-after.png)','</details>',
              'Checks passed for the first-gate half-plane rule, an independent singlet polygon calculation, unchanged downstream processing, event order, event subsets, parent containment, denominators, and plotted gate geometry.',
              '[Gate comparison CSV]('+root+'gate-comparison.csv) · [Results and coordinates]('+root+'results.json) · [Digitization configuration]('+root+'configuration.json) · [Original user drawing]('+root+'user-guidance.png)']
    return lines


def main():
    ASSETS.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((ROOT/'data/manifests/public-files.json').read_text())
    prior = json.loads((ROOT/'reports/local/testing/validation.json').read_text())
    prior_gates = {(w['workspace'], c['sample'], g['gate']): g
                   for w in prior['workspaces'] for c in w['cases'] for g in c['gates']}
    batch = json.loads((ROOT/'reports/local/testing/opencyto/validation.json').read_text())
    fitted = {c['input']: c for c in batch['cases'] if c['status'] == 'passed'}
    fcs_rows = [r for r in manifest['files'] if r['filename'].lower().endswith('.fcs') and (ROOT/r['path']).exists()]
    index = exact_index([r for r in fcs_rows if r['dataset'] == 'car-nk-knockin'])
    authored = {}
    gate_records = []
    plot_records = []
    for row in manifest['files']:
        if row['dataset'] != 'car-nk-knockin' or not row['filename'].endswith('.wsp') or not (ROOT/row['path']).exists():
            continue
        path = verify_source(row)
        structure = fk.Workspace(str(path), load_missing_file_data=True)
        ids = [sid for sid in structure.get_sample_ids(loaded_only=False) if sid in index]
        samples = [fk.Sample(str(verify_source(index[sid])), sample_id=sid, preprocess=False) for sid in ids]
        workspace = fk.Workspace(str(path), fcs_samples=samples, load_missing_file_data=True)
        workspace.analyze_samples(use_mp=False)
        for sid in workspace.get_sample_ids():
            source = index[sid]
            slug = hashlib.sha256(source['path'].encode()).hexdigest()[:16]+'.png'
            gates = workspace_plot(workspace, sid, ASSETS/slug)
            for g in gates:
                previous = prior_gates[(row['filename'], sid, g['gate'])]
                if (g['count'], g['parent_count']) != (previous['count'], previous['parent_count']):
                    raise ValueError('Plot counts differ from the tested workspace results')
                g['compensation_omission_membership_changes'] = previous['compensation_omission_membership_changes']
            record = {'dataset': source['dataset'], 'filename': sid, 'path': source['path'], 'role': source['role'],
                      'events': workspace.get_sample(sid).event_count, 'image': slug, 'mode': 'Author gate replay',
                      'workspace': row['filename'], 'selected': gates[-1]['count'],
                      'parent_count': gates[-1]['parent_count'], 'percent_of_parent': gates[-1]['percent_of_parent'],
                      'source_checksum': source['checksum'], 'source_checksum_algorithm': source['checksum_algorithm'], 'gates': gates}
            authored[source['path']] = record
            for gate in gates:
                gate_records.append({'sample': sid, 'workspace': row['filename'], **gate})
    for row in fcs_rows:
        if row['path'] in authored:
            plot_records.append(authored[row['path']])
            continue
        path = verify_source(row)
        sample = fk.Sample(str(path), preprocess=False)
        slug = hashlib.sha256(row['path'].encode()).hexdigest()[:16]+'.png'
        selected = raw_plot(row, sample, fitted.get(row['path']), ASSETS/slug)
        plot_records.append({'dataset': row['dataset'], 'filename': row['filename'], 'path': row['path'],
                             'role': row['role'], 'events': sample.event_count, 'image': slug,
                             'mode': 'openCyto FSC engineering gate' if selected is not None else 'Raw scatter only',
                             'selected': selected, 'parent_count': sample.event_count if selected is not None else None,
                             'percent_of_parent': 100*selected/sample.event_count if selected is not None else None,
                             'source_checksum': row['checksum'], 'source_checksum_algorithm': row['checksum_algorithm']})
    if len(plot_records) != prior['summary']['fcs_checksum_and_parse_passed']:
        raise ValueError('Scatterplot coverage does not match tested FCS inventory')
    summaries = {}
    for dataset in sorted({r['dataset'] for r in plot_records}):
        group = [r for r in plot_records if r['dataset'] == dataset]
        ordered = sorted(group, key=lambda r: (r['percent_of_parent'] is None,
                         r['percent_of_parent'] if r['percent_of_parent'] is not None else 0, r['filename']))
        positions = np.linspace(0, len(ordered)-1, min(12, len(ordered)), dtype=int)
        chosen = [ordered[i] for i in positions]
        sheet = dataset+'-overview.png'
        contact_sheet(chosen, ASSETS/sheet)
        summaries[dataset] = {'files': len(group), 'events': sum(r['events'] for r in group), 'overview': sheet,
                              'overview_files': [r['filename'] for r in chosen]}
    write_csv(ASSETS/'file-results.csv', plot_records,
              ['dataset', 'filename', 'role', 'events', 'mode', 'selected', 'parent_count', 'percent_of_parent', 'image', 'source_checksum_algorithm', 'source_checksum'])
    write_csv(ASSETS/'author-gate-results.csv', gate_records,
              ['sample', 'workspace', 'gate', 'parent', 'count', 'parent_count', 'percent_of_parent', 'events_plotted', 'geometry_membership_verified', 'compensation_omission_membership_changes'])
    receipt = {'files_plotted': len(plot_records), 'all_events_plotted': sum(r['events'] for r in plot_records),
               'mode_counts': dict(Counter(r['mode'] for r in plot_records)), 'author_gate_panels': len(gate_records),
               'fsc_gate_geometry_checks': len(fitted), 'author_geometry_checks': len(gate_records),
               'subsampling': 'none', 'density_color': 'events per 100x100 bin; log color scale; every event plotted',
               'source_manifest_sha256': hashlib.sha256((ROOT/'data/manifests/public-files.json').read_bytes()).hexdigest(),
               'by_dataset': summaries, 'files': plot_records}
    image_names = [r['image'] for r in plot_records]+[s['overview'] for s in summaries.values()]
    receipt['figure_sha256'] = {n: hashlib.sha256((ASSETS/n).read_bytes()).hexdigest() for n in image_names}
    receipt['data_sources'] = [{k:d[k] for k in ['id','title','url','license']} for d in manifest['datasets']]
    register_reviews(receipt)
    (ASSETS/'plot-manifest.json').write_text(json.dumps(receipt, indent=2)+'\n')
    write_page(plot_records, gate_records, summaries, prior, batch)
    write_gallery(plot_records, receipt)
    print(json.dumps({k:v for k,v in receipt.items() if k not in ['files','by_dataset']}, indent=2))


def write_page(records, gates, summaries, prior, batch):
    current_receipt=json.loads((ROOT/'reports/testing-validation.json').read_text())
    test_count=current_receipt['python_tests']['passed']
    lines = ['# Flow cytometry testing: scatterplots and results',
      'Existing development data · checked October 18, 2026 · FlowKit 1.3.2 / openCyto 2.22.0',
      '**159 FCS files now have event scatterplots.** All 1,234,498 events are represented without display subsampling. Pink boundaries show original tested gates; orange boundaries identify the user-guided revision. Counts and percentages are computed on complete event memberships.',
      '[Author gate plots](#author-gating-hierarchies) · [HER2 CAR-T plots](#her2-car-t-engineering-gates) · [Other datasets](#other-existing-data) · [Complete file index](#complete-file-index) · [Methods and limits](#methods-and-limits)',
      '## Test coverage',
      '| Test | Result | Scope |', '|---|---|---|',
      '| Source integrity and parsing | 159 / 159 available files; 1,234,498 finite events | Six cataloged FCS files remain unavailable |',
      '| Fresh openCyto fitting | 71 / 71 available HER2 files | Raw FSC-A engineering threshold; no biological identity |',
      '| openCyto → FlowKit transfer | 397,897 events; **zero membership mismatches** | Same fitted thresholds |',
      '| FSC GatingML roundtrip | 71 / 71 passed schema and event membership checks | Supported engineering gates |',
      '| Author workspace replay | 3 workspaces, 7 matching files, 28 gates | Order, subset, nesting, and parent-denominator checks passed |',
      '| Compensation omission control | Changed membership in 3 / 7 file cases | Confirms compensation can be consequential |',
      '| Author GatingML export | **0 / 7 usable exports** | Unsupported exported FlowJo strategies; original workspaces remain replayable |',
      f'| Regression suite | {test_count} tests passed | Includes membership, mapping, denominator, export, and digitized-geometry safeguards |',
      '| Figure geometry verification | 28 author panels + 71 FSC thresholds passed | Drawn coordinates reproduce gate membership |',
      '**These results establish engineering consistency. Biological accuracy, agreement with FlowJo, independent-donor generalization, and benefit versus an agent without this skill have not been established.**',
      'Downloads: [file-level results CSV](assets/testing/file-results.csv) · [author gate counts CSV](assets/testing/author-gate-results.csv) · [plot manifest](assets/testing/plot-manifest.json) · [testing receipt](../reports/testing-validation.json). The CSVs contain aggregate event counts, not event-level measurements. [Source deposits and licenses](DATASETS.md) retain their original attribution and terms.',
      '## Author gating hierarchies',
      'The CAR-NK author workspaces provide actual scatter → singlet → live → CAR hierarchies. Each four-panel figure shows only the events in that gate’s parent. Axes retain the workspace compensation and transformation settings. Click a sample name for its full-resolution figure.',
      '| Workspace | File / scatterplot | Input events | Live events | CAR / live | CAR (% of live) | CAR events changed without compensation |', '|---|---|---:|---:|---:|---:|---:|']
    authored = [r for r in records if r['mode']=='Author gate replay']
    for r in authored:
        live = next(g['count'] for g in r['gates'] if g['gate']=='Live')
        changes=next(g['compensation_omission_membership_changes'] for g in r['gates'] if g['gate']=='CAR')
        lines.append(f"| {r['workspace']} | [{r['filename']}](assets/testing/{r['image']}) | {r['events']:,} | {live:,} | {r['selected']:,} / {r['parent_count']:,} | {r['percent_of_parent']:.2f}% | {changes:,} |")
    lines += ['The 76-event `aftersort_APC+.fcs` file has only 38 live events. Its 97.37% CAR/live fraction is 37 events out of 38 and should not be interpreted as a precise product-quality estimate.',
              '**High-CAR example and matching RNP file**']
    for name in ['NK Cells_Her2_CAR.fcs','NK Cells_RNP_Her2.fcs']:
        r=next(r for r in authored if r['filename']==name)
        lines.append(f"![{name}: scatter, singlet, live, and CAR gate overlays](assets/testing/{r['image']})")
    lines += ['<details>', '<summary>Show all seven author hierarchy figures</summary>', '']
    for r in authored:
        lines += [f"**{r['workspace']} · {r['filename']}**", f"![{r['filename']} gate hierarchy](assets/testing/{r['image']})"]
    lines += ['</details>', '## HER2 CAR-T engineering gates',
      'All 71 available HER2 files have FSC-A versus SSC-A and FSC-A versus FSC-H scatterplots. The vertical pink line is the separately fitted openCyto FSC-A threshold; the selected region is to its right. The second panel is a scatter view, not an automatically fitted singlet gate. Fluorescence compensation is not used for these scatter-only gates.',
      'Retained fractions range from **0.213% to 76.719%**. This variation requires biological review; zero engine mismatches does not establish that appropriate cells were selected.',
      'The overview below includes 12 files spaced evenly through the sorted retained-fraction range, including both extremes. Every one of the 71 full-resolution figures is linked in the complete file index.',
      '![HER2 scatterplot overview: low through high retained fraction](assets/testing/her2-car-t-overview.png)',
      '## Other existing data',
      'The adjacent GFP, Treg, and remaining NK files have raw FSC-A/SSC-A and FSC-A/FSC-H plots. No biological gates are invented for these files. Control and derivative roles are preserved in the full index. These are supporting/raw QC views, not additional autogating validations.']
    for dataset in ['t-cell-gfp-knockin','treg-characterization','car-nk-knockin']:
        summary=summaries[dataset]
        lines += [f"### {dataset}",f"{summary['files']} files · {summary['events']:,} events. Overview includes up to 12 files; all files are linked below.",f"![{dataset} scatterplot overview](assets/testing/{summary['overview']})"]
    lines += ['## Complete file index', 'Each linked image contains actual event scatterplots. Percentages below use the named denominator; empty cells mean no gate was applied. File counts are not donor or biological-sample counts.']
    for dataset in sorted(summaries):
        group=[r for r in records if r['dataset']==dataset]
        lines += ['<details>',f'<summary>{dataset}: all {len(group)} scatterplot figures and results</summary>','',
                  '| File / scatterplot | Source role | Events | Analysis | Selected / denominator | Percent |', '|---|---|---:|---|---:|---:|']
        for r in group:
            ratio = f"{r['selected']:,} / {r['parent_count']:,}" if r['selected'] is not None else '—'
            pct = f"{r['percent_of_parent']:.3f}%" if r['percent_of_parent'] is not None else '—'
            denom = ' (live parent)' if r['mode']=='Author gate replay' else ' (all events)' if r['selected'] is not None else ''
            lines.append(f"| [{r['filename']}](assets/testing/{r['image']}) | {r['role']} | {r['events']:,} | {r['mode']}{denom} | {ratio} | {pct} |")
        lines += ['', '</details>']
    lines += ['## Methods and limits',
      '- **Display:** every event is plotted, with local density encoded by a logarithmic color scale (dark purple: sparse; yellow: dense). No event subsampling or quantile clipping is used. Author panels restrict displayed events to their actual parent gates.',
      '- **Geometry:** the author figures use the same preprocessing routine as pinned FlowKit’s own plotting implementation. The figure builder reapplies each gate to those coordinates and verifies exact full-event membership. Each drawn HER2 threshold is independently checked against its saved R membership.',
      '- **Processing:** author axes explicitly state linear/biexponential coordinates and compensation references. No second compensation is applied. Raw scatter panels use acquisition-scaled FCS values without fluorescence compensation or display transforms.',
      '- **Donors:** the HER2 and GFP studies share one reported source donor; Treg represents another reported donor group. NK donor identities remain unresolved. Repeated files and control/exported/concatenated data do not increase donor counts.',
      '- **Excluded representations:** the processed 28-patient fluorescence objects do not retain original acquisition gates. The five CyTOF pilot files are a separate modality. Neither is included in this fluorescence FCS plot set.',
      '- **Missing inputs:** five HER2 FCS files, one cataloged NK FCS file, and `tSNE.wsp` remain unavailable. `Sorting.wsp` additionally references `3days_aftersort_APC+.fcs`, which has no exact matching source filename in the manifest. The different `2days_aftersort_APC+.fcs` filename is never substituted.',
      '- **Portability:** the seven author GatingML exports fail schema validation, including unsupported FlowJo biexponential serialization, invalid XML identifiers, empty fluorochrome labels, and missing compensation references. Workspaces are replayed directly; transformations are not approximated to force export.',
      '- **Validation boundary:** author labels are reference candidates, not independent truth. No CAR release criterion, potency conclusion, rare-population sensitivity, or biological accuracy is inferred.',
      '## Reproduce and inspect evidence',
      'Run from the repository root with the existing data and recorded R image available. No command below downloads data.',
      '```sh\nuv sync --locked\nuv run pytest -q\nuv run scripts/validate_existing_data.py\nuv run scripts/validate_opencyto_batch.py\nuv run scripts/build_scatter_report.py\n```',
      'Raw FCS files, per-event memberships, logs, and invalid diagnostic XML stay under ignored `data/raw/` and `reports/local/`. Curated figures, aggregate result tables, and plot provenance are included here so this GitHub page is usable without local files. The offline gallery is `docs/assets/testing/index.html`; open it locally to search all 159 figures.',
      'The next biological test requires reconciled HER2 markers, controls, and compensation state plus expert-reviewed reference memberships. Collection remains paused, and FlowSOM remains deferred.']
    revision=review_section()
    if revision:
        position=lines.index('## Author gating hierarchies')
        lines[position:position]=revision
        lines[3]='[User-guided revision](#user-guided-revision-nk-her2-v1) · '+lines[3]
        for i,line in enumerate(lines):
            if line.startswith('```sh'):
                lines[i]=line.replace('uv run scripts/build_scatter_report.py',
                                      'uv run scripts/apply_review_guidance.py\nuv run scripts/build_scatter_report.py')
    # Blank lines between blocks preserve tables, images, and details on GitHub.
    text='\n\n'.join(lines).replace('—','Not applied')
    # Table rows need consecutive lines to render as one Markdown table.
    text=text.replace('|\n\n|','|\n|')
    (ROOT/'docs/TESTING.md').write_text(text+'\n')
    renderer=MarkdownIt('commonmark', {'html':True}).enable('table')
    def heading_open(tokens, idx, options, env):
        slug=re.sub(r'[^a-z0-9 -]', '', tokens[idx+1].content.lower()).replace(' ','-')
        return f'<{tokens[idx].tag} id="{slug}">'
    renderer.renderer.rules['heading_open']=heading_open
    body=renderer.render(text)
    body=re.sub(r'<img\b[^>]*src="([^"]+)"[^>]*>',
                lambda match: '<a href="'+match.group(1)+'" title="Open full-resolution figure">'+match.group(0)+'</a>',body)
    body=body.replace('href="../reports/testing-validation.json"', 'href="assets/testing/testing-receipt.json"')
    (ASSETS/'testing-receipt.json').write_bytes((ROOT/'reports/testing-validation.json').read_bytes())
    standalone='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Flow cytometry testing: scatterplots and results</title>
<style>body{font:16px/1.6 system-ui;color:#182b3b;background:#f1f5f8;margin:0}main{max-width:1180px;margin:auto;padding:30px 36px;background:white}h1{font-size:32px;line-height:1.2;color:#12374b}h2{margin-top:44px;border-bottom:2px solid #dae6ed;padding-bottom:8px;color:#12374b}h3{margin-top:30px}a{color:#006d91}img{max-width:100%;height:auto;border:1px solid #dce4ea;border-radius:6px}table{border-collapse:collapse;font-size:14px;display:block;overflow-x:auto;width:100%;margin:20px 0}th,td{padding:10px 12px;border:1px solid #dce4ea;text-align:left}th{background:#e9f2f7}tbody tr:nth-child(even){background:#f7f9fb}details{border:1px solid #cedde6;border-radius:6px;padding:14px;margin:18px 0}summary{cursor:pointer;font-weight:650}pre{padding:18px;background:#eff4f7;overflow:auto}code{font-size:14px}li{margin:10px 0}.top{background:#12374b;color:white;padding:15px 24px;position:sticky;top:0;z-index:2}.top a{color:white;margin-right:20px}h2,h3{scroll-margin-top:75px}@media(max-width:700px){main{padding:20px 14px}.top{position:static}h1{font-size:26px}}</style>
<nav class="top"><a href="#user-guided-revision-nk-her2-v1">Reviewed gates</a><a href="#author-gating-hierarchies">Author gates</a><a href="#her2-car-t-engineering-gates">HER2 scatterplots</a><a href="#complete-file-index">All files</a><a href="assets/testing/index.html">Search gallery</a></nav><main>'''+body+'''</main></html>'''
    (ROOT/'docs/TESTING.html').write_text(standalone)


def write_gallery(records, receipt):
    cards=[]
    review_file=ASSETS/'reviews/nk-her2-v1/results.json'
    if review_file.exists():
        review=json.loads(review_file.read_text())
        cards.append('<article data-search="user guided reviewed revision nk her2 car nk cells_her2_car.fcs"><h2>User-guided revision: '+html.escape(review['sample'])+'</h2><p>Same 30,000-event source file; manually digitized early gates, recomputed downstream parents. Orange: revised boundaries; gray: original; pink: retained downstream geometry.</p><a href="reviews/nk-her2-v1/revised-hierarchy.png"><img src="reviews/nk-her2-v1/revised-hierarchy.png" alt="User-guided revised gate hierarchy"></a><p><a href="reviews/nk-her2-v1/gate-comparison.csv">Revised gate counts</a> · <a href="reviews/nk-her2-v1/before-after.png">Before and after</a></p></article>')
    for r in records:
        caption=f"{r['filename']} · {r['events']:,} events · {r['mode']}"
        cards.append(f'<article data-search="{html.escape((r["dataset"]+" "+r["filename"]+" "+r["mode"]).lower())}"><h2>{html.escape(r["filename"])}</h2><p>{html.escape(r["dataset"])} · {r["events"]:,} events · {html.escape(r["mode"])}</p><a href="{r["image"]}"><img loading="lazy" src="{r["image"]}" alt="{html.escape(caption)}"></a></article>')
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Cell therapy flow: event scatterplots</title>
<style>body{font:16px system-ui;background:#f4f7fa;color:#162538;margin:0}header{background:#162538;color:white;padding:28px;position:sticky;top:0;z-index:2}h1{font-size:25px;margin:0 0 10px}input{font:inherit;padding:12px;width:min(680px,85%);border-radius:6px;border:0}main{max-width:1350px;margin:auto;padding:24px}article{background:white;padding:18px;margin-bottom:24px;border-radius:10px;box-shadow:0 1px 8px #dde3e9}h2{font-size:19px;overflow-wrap:anywhere}img{width:100%;height:auto}p{line-height:1.5}a{color:#0e5873}</style>
<header><h1>Cell therapy flow: event scatterplots</h1><p>159 FCS files · 1,234,498 events · 71 engineering fits · 7 author hierarchies. Biological accuracy untested.</p><label for="search">Filter by filename, dataset, or analysis</label><br><input id="search" placeholder="For example: her2-car-t, RNP, author gate"><span id="count"></span></header><main><p>Every event is shown. Pink lines are tested gates; color shows density. Author panels show only parent events, with workspace transformations. Other panels show raw acquisition-scaled scatter. Click an image for full resolution. Tables and provenance: <a href="file-results.csv">file results</a> · <a href="author-gate-results.csv">gate counts</a> · <a href="plot-manifest.json">manifest</a>.</p>'''+''.join(cards)+'''</main><script>const cards=[...document.querySelectorAll('article')],search=document.querySelector('#search');function filter(){const q=search.value.toLowerCase();let n=0;cards.forEach(c=>{c.hidden=!c.dataset.search.includes(q);if(!c.hidden)n++});document.querySelector('#count').textContent=' '+n+' figures'}search.addEventListener('input',filter);filter();</script></html>'''
    if review_file.exists():
        page=page.replace('7 author hierarchies. Biological accuracy untested.','7 author hierarchies · 1 user-guided variant of an existing file. Biological accuracy untested.')
    (ASSETS/'index.html').write_text(page)


if __name__=='__main__':
    main()
