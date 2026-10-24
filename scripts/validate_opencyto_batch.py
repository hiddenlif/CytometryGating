"""Fit engineering FSC gates on existing HER2 files and verify event transfer."""

import json
import subprocess
from collections import Counter

from validate_existing_data import ROOT, verify_source
from verify_gate_transfer import verify

IMAGE = "cell-therapy-autogating-r:0.1.0"


def main():
    output = ROOT / "reports/local/testing/opencyto"
    output.mkdir(parents=True, exist_ok=True)
    image_id = subprocess.check_output(
        ["docker", "image", "inspect", IMAGE, "--format", "{{.Id}}"], text=True
    ).strip()
    manifest = json.loads((ROOT / "data/manifests/public-files.json").read_text())
    rows = [
        r
        for r in manifest["files"]
        if r["dataset"] == "her2-car-t" and r["filename"].lower().endswith(".fcs")
    ]
    cases, missing = [], []
    for row in rows:
        if not (ROOT / row["path"]).exists():
            missing.append(row["path"])
            continue
        verify_source(row)
        destination = output / str(len(cases)).zfill(3)
        cases.append(
            {"input": row["path"], "output": str(destination.relative_to(ROOT))}
        )
    if not cases:
        raise ValueError("No available HER2 FCS files to test")
    case_file = output / "cases.json"
    result_file = output / "r-batch.json"
    case_file.write_text(json.dumps(cases, indent=2) + "\n")
    with (output / "r-batch.log").open("w") as log:
        subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{ROOT}:/work",
                IMAGE,
                "scripts/opencyto_batch.R",
                str(case_file.relative_to(ROOT)),
                str(result_file.relative_to(ROOT)),
            ],
            cwd=ROOT,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=True,
        )
    results = json.loads(result_file.read_text())
    for row in results:
        if row["status"] != "fitted":
            continue
        dest = ROOT / row["output"]
        try:
            row["transfer"] = verify(ROOT / row["input"], dest)
            row["gate"] = json.loads((dest / "r-gate.json").read_text())
            row["status"] = "passed"
        except Exception as exc:
            row.update(status="transfer_failed", error=f"{type(exc).__name__}: {exc}")
    summary = {
        "r_image": image_id,
        "dataset": "her2-car-t",
        "cataloged_fcs": len(rows),
        "available_tested_fcs": len(cases),
        "not_downloaded_fcs": len(missing),
        "outcomes": dict(Counter(r["status"] for r in results)),
        "events_compared": sum(r.get("transfer", {}).get("events", 0) for r in results),
        "membership_mismatches": sum(
            r.get("transfer", {}).get("membership_mismatches", 0) for r in results
        ),
        "claim": "Independent per-file openCyto FSC-A mindensity fitting and exact FlowKit transfer, including validated GatingML roundtrip. Engineering only; no biological identity or accuracy claim.",
    }
    (output / "validation.json").write_text(
        json.dumps({"summary": summary, "cases": results, "missing": missing}, indent=2)
        + "\n"
    )
    print(json.dumps(summary, indent=2))
    if any(r["status"] != "passed" for r in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
