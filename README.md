# Cytometry Gating: Public FCS Engineering and Gate Transfer

An early development repository for reviewable cell therapy flow cytometry analysis with **openCyto** and **FlowKit**. The initial application is CAR-T process development and characterization. CAR-NK and other T-cell datasets are separate compatibility cohorts.

Current capabilities: retrieve public FCS files with checksum verification, inventory channels and event counts, detect identical ordered event matrices, and run an engineering gate-transfer check between openCyto and FlowKit. **Biological population gating and expert-agreement performance have not been validated.**

## Engineering review

Start with the [scatterplots and results](docs/TESTING.md), [architecture and reproducibility](docs/ENGINEERING.md), and [automated checks](https://github.com/hiddenlif/CytometryGating/actions/workflows/validate.yml). The workflow runs the 22 regression cases in a non-root, read-only Python container without runtime networking and checks committed report assets. Real-FCS and R checks are separately documented local executions.

## Setup

Requires Python 3.12, [uv](https://docs.astral.sh/uv/), and Docker with several GB of available storage for the R environment.

```sh
uv sync --locked
docker build -t cell-therapy-autogating-r:0.1.0 -f docker/Dockerfile .
```

The Python dependency graph is frozen in `uv.lock`. The R base image is bound to its multi-platform digest and Bioconductor 3.22. The Docker build installs R packages from repositories and records their exact versions in `/opt/cytometry-packages.tsv`; this is a version receipt, not a complete immutable R dependency mirror. Preserve the built image or bind its resulting digest for exact reruns.

## Public starter data

The catalog contains **165 FCS files**, four FlowJo workspaces, and one dataset README across four datasets, approximately **185.5 MB** in total. These are file counts, not established unique biological sample or donor counts. See [the dataset catalog](docs/DATASETS.md).

```sh
# Closest initial match: 76 HER2 CAR-T experiment FCS files.
uv run scripts/fetch_public_data.py --dataset her2-car-t
# Optional: download every cataloged dataset, including adjacent cohorts.
uv run scripts/fetch_public_data.py --all
uv run scripts/inspect_fcs.py
```

For a single downloaded cohort, use `uv run scripts/inspect_fcs.py --dataset her2-car-t`. To inspect downloaded author workspace structures, use `uv run scripts/inspect_workspaces.py`; that command does not execute or validate their biological gates.

Downloads are verified against repository checksums and stay under ignored `data/raw/`. They are not bundled in Git or covered by the software license. A failed download is reported in `reports/local/download-receipt.json`; no failed or partial file is accepted. Retries are bounded. `scripts/catalog_public_data.py` explicitly refreshes the catalog from repository APIs; refreshing can change the selected version and must be reviewed.

The [initial setup receipt](reports/setup-validation.json) records **159 successfully downloaded and parsed FCS files**, six failed FCS downloads, and one failed workspace download. The source methods report a single shared leukopak donor across the CAR/GFP knock-in experiments and one Treg donor. This is a useful engineering starter pool with limited donor diversity; it is not a multi-donor robustness benchmark.

## Run the openCyto / FlowKit engineering check

```sh
docker run --rm -v "$PWD:/work" cell-therapy-autogating-r:0.1.0 \
  scripts/opencyto_smoke.R \
  data/raw/her2-car-t/53785433_0.625ng_B7.fcs reports/local/smoke
uv run scripts/verify_gate_transfer.py \
  data/raw/her2-car-t/53785433_0.625ng_B7.fcs reports/local/smoke
```

openCyto estimates a one-dimensional density threshold on raw FSC-A. FlowKit replays that exact threshold and compares every event membership. Outputs include GatingML, counts, gate parameters, R session information, and a comparison receipt. This deliberately unlabeled scatter gate tests plumbing; it does not establish a lymphocyte, live-cell, or CAR-positive gate, nor biological accuracy. No fluorescence compensation or unmixing is performed in this check.

```sh
uv run pytest -q
```

## Agent skill

The draft skill is at `skills/cell-therapy-autogating/SKILL.md`. Clone the whole repository, install that skill folder with your agent's normal skill installation method, and make the companion repository location available as `CELL_THERAPY_AUTOGATING_REPO`. Its supporting reference explains the executable workflow. Installing the skill does not itself establish a validated analysis method.

Biological interpretation requires documented marker mapping, controls, compensation/unmixing state, transformations, sample relationships, and expert reference gates. There are no generic release limits or automatic product-release decisions.

## Next work

The [first testing pass](docs/TESTING.md) reparsed all 159 available FCS files, fitted and transferred engineering FSC gates on 71 HER2 files, and replayed three author workspaces. See the [testing receipt](reports/testing-validation.json) for results and unsupported export paths. Data collection is paused; work now focuses on testing the existing data.

The report now includes actual event scatterplots for every available fluorescence FCS file, author gate overlays, full counts and denominators, dataset overviews, and a complete figure index. Curated figures and aggregate CSV results are available directly on GitHub under `docs/assets/testing/`.

For local review without GitHub sign-in, open `docs/TESTING.html` in a browser. It contains the full organized report and links to a searchable gallery of all 159 figures.

The report also includes a user-guided revision of the first two gates for `NK Cells_Her2_CAR.fcs`, with revised downstream counts and a before/after comparison. The original author analysis remains available. This reviewed variant is approximately digitized from the user's drawing and is not an additional sample or an automatic-gating validation.

The [donor-focused search](docs/DONOR-DISCOVERY-2026-10-18.md) adds a verified 28-patient processed-flow cohort, a separately tracked mass-cytometry archive, and access-qualified raw-data leads. These are separate from the original FCS catalog; processed objects and mass cytometry do not establish raw fluorescence gating performance. See the [discovery receipt](reports/donor-discovery-validation.json).

See [ROADMAP.md](docs/ROADMAP.md). The next milestone is an expert-reviewed panel and control strategy on the HER2 CAR-T data, followed by event-level and frequency comparisons on genuinely held-out donors/runs. All files inspected during setup are development data. A separate FlowSOM repository is deferred.
