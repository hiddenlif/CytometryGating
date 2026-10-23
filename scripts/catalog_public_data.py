"""Refresh public metadata snapshots and a file manifest. No FCS downloads."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = ROOT / "data" / "manifests"
FIGSHARE = {
    "her2-car-t": "28824383",
    "t-cell-gfp-knockin": "28817957",
    "treg-characterization": "28817822",
}


def get_json(url):
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    return response.json()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def safe_name(name):
    if Path(name).name != name or name in {".", ".."} or "\\" in name:
        raise ValueError(f"Unsafe repository filename: {name!r}")
    return name


def main():
    rows, datasets = [], []
    for key, article_id in FIGSHARE.items():
        meta = get_json(f"https://api.figshare.com/v2/articles/{article_id}")
        # Bind the version, rather than silently following a moving article.
        version = meta["version"]
        meta = get_json(f"https://api.figshare.com/v2/articles/{article_id}/versions/{version}")
        write_json(MANIFESTS / f"{key}.source.json", meta)
        datasets.append({
            "id": key, "title": meta["title"], "version": version,
            "url": meta["url_public_html"], "doi": meta.get("doi"),
            "license": meta["license"]["name"],
            "scope": "CAR-T engineering" if key == "her2-car-t" else "adjacent T-cell engineering/phenotyping",
            "verified_unique_donors": None, "verified_unique_biosamples": None,
            "source_reported_experiment_donors": 1,
            "source_reported_donor_group": "crispr-study-treg-donor" if key == "treg-characterization" else "crispr-study-knockin-leukopak-donor",
            "donor_count_evidence": {
                "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC12339676/",
                "section": "Primary human T cell procurement and isolation",
                "limit": "Experiment-level report; acquisition-to-specimen identity and controls still require reconciliation.",
            },
        })
        for f in meta["files"]:
            filename = safe_name(f["name"])
            role = "unresolved_acquisition"
            if "compensation" in filename.lower():
                role = "compensation_control"
            elif "unstained" in filename.lower():
                role = "unstained_control"
            rows.append({
                "dataset": key, "repository_file_id": str(f["id"]),
                "filename": filename, "path": f"data/raw/{key}/{f['id']}_{filename}",
                "url": f["download_url"], "bytes": f["size"],
                "checksum_algorithm": "md5", "checksum": f["computed_md5"],
                "role": role, "donor_id": None, "biosample_id": None,
                "split": "development_only",
            })

    key, dataset_id, version = "car-nk-knockin", "4cwny84gs2", 1
    base = f"https://data.mendeley.com/public-api/datasets/{dataset_id}"
    meta = get_json(f"{base}/snapshot/{version}")
    folders = get_json(f"{base}/folders/{version}")
    files = []
    for folder_id in ["root", *[f["id"] for f in folders]]:
        start = 0
        while True:
            batch = get_json(f"{base}/files?folder_id={folder_id}&version={version}&$start={start}&$limit=1000")
            for f in batch:
                f["folder_id"] = folder_id
            files.extend(batch)
            if len(batch) < 1000:
                break
            start += len(batch)
    write_json(MANIFESTS / f"{key}.source.json", {"metadata": meta, "folders": folders, "files": files})
    datasets.append({
        "id": key, "title": meta["name"], "version": version,
        "url": f"https://data.mendeley.com/datasets/{dataset_id}/{version}",
        "doi": meta["doi"], "license": meta["licence"]["short_name"],
        "scope": "CAR-NK, separate exploratory compatibility cohort",
        "verified_unique_donors": None, "verified_unique_biosamples": None,
    })
    for f in files:
        filename = safe_name(f["filename"])
        role = "unresolved_acquisition"
        if filename.lower().startswith("export_"):
            role = "exported_subset"
        elif filename.lower().startswith("concat"):
            role = "concatenation"
        elif filename.lower().endswith(".wsp"):
            role = "author_workspace"
        elif not filename.lower().endswith(".fcs"):
            role = "documentation"
        rows.append({
            "dataset": key, "repository_file_id": f["id"],
            "filename": filename, "path": f"data/raw/{key}/{f['id']}_{filename}",
            "url": f["content_details"]["download_url"], "bytes": f["size"],
            "checksum_algorithm": "sha256", "checksum": f["content_details"]["sha256_hash"],
            "role": role, "donor_id": None, "biosample_id": None,
            "split": "development_only",
        })
    write_json(MANIFESTS / "public-files.json", {
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "datasets": datasets, "files": rows,
        "counting_rule": "FCS file counts are not unique biological sample or donor counts. All inspected files are development data.",
    })
    for dataset in datasets:
        group = [r for r in rows if r["dataset"] == dataset["id"]]
        print(dataset["id"], "FCS", sum(r["filename"].lower().endswith(".fcs") for r in group), "all files", len(group))


if __name__ == "__main__":
    main()
