"""Retrieve explicitly selected discovery files using the shared integrity checks."""

import argparse
import json
from pathlib import Path

from fetch_public_data import fetch

ROOT = Path(__file__).resolve().parents[1]


def main():
    manifest = json.loads((ROOT / "data/discovery/downloads.json").read_text())
    known = sorted({r["dataset"] for r in manifest["files"]})
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=known, action="append", required=True)
    args = parser.parse_args()
    for row in manifest["files"]:
        if row["dataset"] in args.dataset:
            print(fetch(row), flush=True)


if __name__ == "__main__":
    main()
