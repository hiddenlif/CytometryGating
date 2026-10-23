"""Replay the R smoke gate in FlowKit and compare every event membership."""
import argparse
import hashlib
import json
from pathlib import Path

import flowkit as fk
import numpy as np
import pandas as pd
from gatingml_export import export_verified_gatingml


def verify(fcs, result_dir):
    config = json.loads((result_dir / "r-gate.json").read_text())
    if hashlib.md5(fcs.read_bytes()).hexdigest() != config["input_md5"]:
        raise ValueError("FCS file differs from the file used by openCyto")
    sample = fk.Sample(str(fcs), preprocess=False)
    strategy = fk.GatingStrategy()
    strategy.add_gate(fk.gates.RectangleGate("demo_fsc_high", [fk.Dimension(
        config["channel"], range_min=config["lower_bound"], range_max=config["upper_bound"]
    )]), ("root",))
    result = strategy.gate_sample(sample)
    actual = result.get_gate_membership("demo_fsc_high")
    expected_frame = pd.read_csv(result_dir / "r-membership.csv")
    if not np.array_equal(expected_frame.event_index_0, np.arange(sample.event_count)):
        raise ValueError("R membership indices do not match source event order")
    if not expected_frame.member.isin([0, 1]).all():
        raise ValueError("R membership contains non-binary values")
    expected = expected_frame.member.to_numpy(dtype=bool)
    if len(actual) != len(expected):
        raise ValueError("R and FlowKit event counts differ")
    mismatches = int(np.count_nonzero(actual != expected))
    report = {
        "events": len(actual), "membership_mismatches": mismatches,
        "openCyto_selected": int(expected.sum()), "flowkit_selected": int(actual.sum()),
        "passed": mismatches == 0,
        "claim": "Agreement for this transferred raw FSC threshold only; no biological accuracy or automatic gate adaptation validation.",
    }
    if sample.event_count != config['event_count'] or int(expected.sum()) != config['selected_count']:
        raise ValueError('R gate summary disagrees with membership')
    export_verified_gatingml(strategy, result_dir / 'smoke-gates.xml', sample=sample)
    report['gatingml_schema_and_membership_roundtrip'] = 'passed'
    (result_dir / "transfer-verification.json").write_text(json.dumps(report, indent=2) + "\n")
    if mismatches:
        raise ValueError(f'{mismatches} openCyto/FlowKit membership mismatches')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fcs", type=Path)
    parser.add_argument("result_dir", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.fcs, args.result_dir), indent=2))


if __name__ == "__main__":
    main()
