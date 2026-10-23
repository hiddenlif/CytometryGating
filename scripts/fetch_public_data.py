"""Download version-bound public files and verify repository checksums."""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parents[1]


def checksum(path, algorithm):
    digest = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fetch(row):
    dest = (ROOT / row["path"]).resolve()
    if not dest.is_relative_to((ROOT / "data/raw").resolve()):
        raise ValueError("Manifest destination escapes data/raw")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        if dest.stat().st_size == row["bytes"] and checksum(dest, row["checksum_algorithm"]) == row["checksum"]:
            return f"verified {row['dataset']}/{row['filename']}"
        raise ValueError(f"Existing file failed verification: {dest}")
    temp = dest.with_name(dest.name + ".part")
    try:
        with requests.Session() as session:
            session.mount("https://", HTTPAdapter(max_retries=Retry(
                total=2, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["GET"],
            )))
            response = session.get(row["url"], stream=True, timeout=(20, 120))
            response.raise_for_status()
            with temp.open("wb") as stream:
                for chunk in response.iter_content(1024 * 1024):
                    stream.write(chunk)
        if temp.stat().st_size != row["bytes"]:
            raise ValueError(f"Size mismatch for {dest.name}")
        if checksum(temp, row["checksum_algorithm"]) != row["checksum"]:
            raise ValueError(f"Checksum mismatch for {dest.name}")
        temp.replace(dest)
    finally:
        temp.unlink(missing_ok=True)
    return f"downloaded {row['dataset']}/{row['filename']}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", action="append", help="Dataset ID; repeat to select several")
    parser.add_argument("--all", action="store_true", help="Download all cataloged datasets")
    args = parser.parse_args()
    manifest = json.loads((ROOT / "data/manifests/public-files.json").read_text())
    known = {d["id"] for d in manifest["datasets"]}
    chosen = known if args.all else set(args.dataset or ["her2-car-t"])
    if chosen - known:
        parser.error(f"Unknown datasets: {sorted(chosen - known)}")
    rows = [r for r in manifest["files"] if r["dataset"] in chosen]
    failures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(fetch, row): row for row in rows}
        for future in concurrent.futures.as_completed(futures):
            row = futures[future]
            try:
                print(future.result(), flush=True)
            except Exception as exc:
                failure = {"path": row["path"], "error": f"{type(exc).__name__}: {exc}"}
                failures.append(failure)
                print(f"FAILED {row['filename']}: {exc}", flush=True)
    receipt = ROOT / "reports/local/download-receipt.json"
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(json.dumps({"requested": len(rows), "succeeded": len(rows) - len(failures), "failures": failures}, indent=2) + "\n")
    if failures:
        raise SystemExit(f"{len(failures)} downloads failed; see {receipt}")


if __name__ == "__main__":
    main()
