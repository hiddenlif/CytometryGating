# Executable workflow

This skill requires the whole companion repository, not just a copied skill folder. Locate `CELL_THERAPY_AUTOGATING_REPO` or the project workspace. Run commands from that root. The canonical repository is `https://github.com/hiddenlif/cell-therapy-autogating`; access depends on its visibility and the user's GitHub permissions.

1. `uv sync --locked` installs pinned Python dependencies.
2. `docker build -t cell-therapy-autogating-r:0.1.0 -f docker/Dockerfile .` builds R dependencies. Check Docker readiness and disk first. Base digest is pinned; package versions are recorded in the image.
3. `uv run scripts/fetch_public_data.py --dataset her2-car-t` downloads the initial CAR-T cohort. `--all` includes adjacent cohorts. Checksums/size must match; failures are saved in `reports/local/download-receipt.json`.
4. `uv run scripts/inspect_fcs.py` inventories cataloged FCS files, reporting missing/failed files, raw event counts, detector/marker labels, and ordered-event duplication. Missing files yield a saved report and nonzero exit. All data are development-only.
5. Run the README engineering check. `scripts/opencyto_smoke.R` fits an unlabeled FSC-A mindensity gate; `scripts/verify_gate_transfer.py` replays that gate in FlowKit and compares event membership. Source-file MD5 binds runs. GatingML is exported.

There is no validated biological panel, CAR threshold, release criterion, expert-agreement benchmark, or untouched evaluation cohort in this setup. See `docs/DATASETS.md` and `docs/ROADMAP.md`. Do not convert the engineering check into a biological conclusion.

For custom FCS files, preserve originals and reconcile metadata/controls first. The current CLI reads the public manifest; it does not yet implement custom-manifest intake. Keep private files out of the public catalog.
