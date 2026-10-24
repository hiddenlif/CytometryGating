"""Inventory downloaded FCS files without assigning biological populations."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path

import flowkit as fk
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def inspect_file(path):
    sample = fk.Sample(str(path), preprocess=False)
    events = sample.get_events(source="raw")
    metadata = sample.get_metadata()
    # Include dimensions and ordered detector names in the data fingerprint.
    fingerprint = hashlib.sha256()
    fingerprint.update(json.dumps([list(events.shape), sample.pnn_labels]).encode())
    fingerprint.update(np.ascontiguousarray(events, dtype="<f8").tobytes())
    return {
        "events": int(events.shape[0]),
        "channel_count": int(events.shape[1]),
        "channels": [
            {"detector": a, "marker": b}
            for a, b in zip(sample.pnn_labels, sample.pns_labels)
        ],
        "event_matrix_sha256": fingerprint.hexdigest(),
        "nonfinite_values": int((~np.isfinite(events)).sum()),
        "spillover_keyword_present": any(
            k.lower() in {"spillover", "spill", "$spillover", "$spill"}
            for k in metadata
        ),
        "acquisition_date": metadata.get("date"),
        "instrument": metadata.get("cyt"),
        "biological_sample_identity": "unresolved",
        "compensation_or_unmixing_status": "unresolved; metadata presence alone does not establish processing state",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "reports/local/fcs-inventory.json"
    )
    parser.add_argument(
        "--dataset",
        action="append",
        help="Restrict inventory to dataset IDs; repeat to select several",
    )
    args = parser.parse_args()
    manifest = json.loads((ROOT / "data/manifests/public-files.json").read_text())
    known = {d["id"] for d in manifest["datasets"]}
    if set(args.dataset or []) - known:
        parser.error("Unknown dataset ID")
    rows = []
    for source in manifest["files"]:
        if args.dataset and source["dataset"] not in args.dataset:
            continue
        if not source["filename"].lower().endswith(".fcs"):
            continue
        path = ROOT / source["path"]
        row = {
            k: source[k]
            for k in ["dataset", "filename", "path", "role", "donor_id", "biosample_id"]
        }
        if not path.exists():
            row["status"] = "not_downloaded"
        else:
            try:
                row.update(inspect_file(path))
                row["status"] = "parsed"
            except Exception as exc:
                row.update(status="parse_failed", error=f"{type(exc).__name__}: {exc}")
        rows.append(row)
    parsed = [r for r in rows if r["status"] == "parsed"]
    groups = {}
    for row in parsed:
        groups.setdefault(row["event_matrix_sha256"], []).append(row["path"])
    result = {
        "flowkit_version": importlib.metadata.version("flowkit"),
        "cataloged_fcs_files": len(rows),
        "parsed_fcs_files": len(parsed),
        "distinct_ordered_event_matrices": len(groups),
        "duplicate_event_matrices": [g for g in groups.values() if len(g) > 1],
        "unique_donors": None,
        "unique_biological_samples": None,
        "source_reported_donor_groups_for_first_three_deposits": sorted(
            {
                d["source_reported_donor_group"]
                for d in manifest["datasets"]
                if "source_reported_donor_group" in d
            }
        ),
        "limitation": "Distinct event matrices do not establish independent samples. Exported subsets and controls remain separate roles. Event fingerprints are order-sensitive.",
        "files": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "files"}, indent=2))
    failures = [r for r in rows if r["status"] != "parsed"]
    if failures:
        raise SystemExit(f"{len(failures)} files missing or failed; see {args.output}")


if __name__ == "__main__":
    main()
