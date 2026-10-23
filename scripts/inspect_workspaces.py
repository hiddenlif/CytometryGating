"""Inspect available author workspace structures without executing their gates."""
import json
from pathlib import Path

import flowkit as fk

ROOT = Path(__file__).resolve().parents[1]


def main():
    manifest = json.loads((ROOT / "data/manifests/public-files.json").read_text())
    records = []
    for row in manifest["files"]:
        path = ROOT / row["path"]
        if path.suffix.lower() != ".wsp":
            continue
        record = {"filename": row["filename"], "status": "missing"}
        if path.exists():
            try:
                workspace = fk.Workspace(str(path), load_missing_file_data=True)
                sample_ids = workspace.get_sample_ids(loaded_only=False)
                record.update(
                    status="parsed_structure_only", sample_references=len(sample_ids),
                    gate_counts=[len(workspace.get_gate_ids(s)) for s in sample_ids],
                )
                if not sample_ids:
                    record.update(status="no_sample_references", error="No usable sample references were parsed")
            except Exception as exc:
                record.update(status="parse_failed", error=f"{type(exc).__name__}: {exc}")
        records.append(record)
    output = ROOT / "reports/local/workspaces.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(records, indent=2) + "\n")
    print(json.dumps(records, indent=2))
    if any(r["status"] != "parsed_structure_only" for r in records):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
