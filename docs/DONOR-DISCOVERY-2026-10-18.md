# Donor-focused public cell therapy data search

Checked 2026-10-18. This pass prioritized identifiable human donors/patients, event-level cytometry, cell therapy relevance, and actual file access. This is a research shortlist, not an exhaustive census. No authors were contacted.

## Verified processed fluorescence-flow cohort: 28 patients

[Yousefian et al., A distinct CAR-T cell phenotype mediates therapeutic response at limited doses](https://www.nature.com/articles/s41467-026-76068-4), [public deposit](https://zenodo.org/records/14711865).

Downloaded and verified publisher MD5 and size for:

- `Fig1_C_CARproduct_overview_sketched_sobj.rds`: 66,121 processed cell records, **27 patient IDs**, 22 assay features.
- `Fig3_A_premanufacturing_PBMCs_sketched_sobj.rds`: 118,601 processed cell records, **28 patient IDs**, 34 assay features.
- `clinical_metadata_Yousefian_etal_2026.csv`: patient-level metadata and modality availability flags.

Both objects contain a FACS assay and per-cell patient identifiers. There are **28 distinct IDs across the objects, with 27 overlapping**. The identifiers match the clinical metadata's 27 product and 28 pre-manufacturing availability flags exactly. The cohort includes B-ALL, CLL, MCL, FL, DLBCL, and DLBCL transformed from FL as six recorded diagnostic categories.

These are genuine cell therapy starting-material/product observations from multiple patients. They are **author-processed, preselected live singlets and sketched cells**, not original FCS acquisitions. They can support downstream phenotyping comparisons and donor-associated variation exploration. They cannot establish performance of debris removal, singlet/viability gating, unmixing, or reconstruction of the original gates. Author annotations are available reference candidates, not independent ground truth. The full product object is also publicly listed, but the current download uses the smaller sketched objects. Do not add the two object sizes as separate patient totals.

Reproduce the inspection after downloading:

```sh
uv run scripts/fetch_discovery_data.py --dataset limited-dose-processed
docker run --rm -v "$PWD:/work" cell-therapy-autogating-r:0.1.0 \
  scripts/inspect_processed_flow.R \
  data/raw/limited-dose-processed/Fig1_C_CARproduct_overview_sketched_sobj.rds \
  data/raw/limited-dose-processed/Fig3_A_premanufacturing_PBMCs_sketched_sobj.rds \
  reports/local/donor-discovery/limited-dose-inspection.json
```

## Public mass-cytometry cohort: five patient-coded series in the archive

[Single-cell signaling network profiling during redox stress reveals dynamic redox regulation in immune cells](https://pmc.ncbi.nlm.nih.gov/articles/PMC12215076/), [Zenodo 11541294](https://zenodo.org/records/11541294).

The public `CAR-T_CyTOF.zip` archive lists **38 actual FCS files**, excluding 38 macOS sidecars. Filenames identify patient codes **1903, 1904, 1905, 1908, and 1909**, each with seven files; three additional files are labeled controls. The paper describes seven patients, but the inspected archive supports only five filename patient codes. Do not claim seven available patients or treat longitudinal files as independent patients. Clinical-table reconciliation beyond the filenames remains outstanding.

This is **mass cytometry of post-treatment blood**, a different modality and stage from fluorescence analysis of manufactured products. Preserve it as a separate exploratory cohort. No FlowSOM analysis is being started.

The range-read inspection script fetches the smallest FCS per patient code when requested. It verifies ZIP member CRCs, records local SHA256, and parses with FlowKit. It does **not** verify the publisher's MD5 of the entire archive when only parts are downloaded. Read `reports/donor-discovery-validation.json` for the actual pilot results.

```sh
uv run scripts/inspect_redox_archive.py --fetch-pilot
```

## Raw fluorescence candidate blocked by encrypted files

[Bispecific chimeric autoantibody receptor T cells eliminate acetylcholine receptor-specific B cells in myasthenia gravis models](https://www.nature.com/articles/s41467-026-76750-7), [Figshare 33059432](https://figshare.com/articles/dataset/33059432).

The paper reports PBMC collection from **16 healthy donors**, in addition to serum samples. Serum donors and engineered cell lines must not be counted as primary cell donors for our purpose. The 1,004,487,639-byte source ZIP was downloaded and its MD5 matched the publisher. Its directory contains 159 FCS entries, **all encrypted**. Attempting to read an FCS raises a password-required error. The dataset metadata has no password field/instructions; the article's availability statement points to the deposit without giving an extraction password.

This is **not a ready-to-use 16-donor FCS cohort**. Accessible content and the mapping of donor identities to deposited experiments remain unverified. Preserve as an author-clarification lead. No password guessing or author contact was performed.

## Strong raw fluorescence candidate with a large archive

[Goodman and Azimi et al., Pooled screening of CAR T cells identifies diverse immune signaling domains for next-generation immunotherapies](https://pmc.ncbi.nlm.nih.gov/articles/PMC9939256/), [raw data](https://zenodo.org/records/7063644), [analysis code](https://zenodo.org/records/7062820).

The source describes arrayed proliferation experiments in **two primary human donors**, and other experiments with different donor counts. The deposit explicitly lists arrayed CTV, exhaustion and differentiation FCS data. The raw-data archive is **43,890,182,808 bytes (43.9 GB)**. A bounded 16 MiB range probe confirmed an accessible gzip/TAR beginning with a large `ctv.sampled.Rdata` member. The full archive was not downloaded because it exceeded available local disk at the initial inspection; FCS counts and donor-to-file mapping are not verified. Do not equate the study-wide donors, scRNA-seq donors, or number of constructs with available flow donors. The paper points to Data file S1 for donor details.

## Other assessed leads

| Lead | Evidence and disposition |
|---|---|
| [Stanford CAR TReg / axi-cel cohort](https://pmc.ncbi.nlm.nih.gov/articles/PMC10917089/), [repository](https://purl.stanford.edu/qb215vz6111) | Study reports CyTOF from 31 patients. Repository access failed TLS verification from this environment. Not counted as downloaded or file-mapped donors. It is also reused by later publications, so those publications do not add independent donors. |
| [VUB HER2 nanoCAR data](https://researchportal.vub.be/en/datasets/her2-targeting-nanobody-based-car-t-cells/) and [B7-H3 nanoCAR data](https://researchportal.vub.be/en/datasets/b7-h3-targeting-nanobody-based-car-t-cells/) | Catalogs list FCS/workspace formats but no usable public file-download link was established. The HER2 paper describes data availability by request. No verified donor totals added. |
| [GLP-1/Urolithin A CAR-T data](https://zenodo.org/records/14725625) | Record is public, files are explicitly restricted. Not counted as open-download data. |
| [MCP CAR-T manufacturing, FR-FCM-Z76E](https://flowrepository.org/id/FR-FCM-Z76E) and [IL-6 receptor engineering, FR-FCM-Z77Y](https://pmc.ncbi.nlm.nih.gov/articles/PMC11148643/) | Relevant mass-cytometry leads. File access/donor mapping unresolved; excluded from verified additions. |
| [BCMA CAR-T single-patient series, FR-FCM-Z4KB](https://flowrepository.org/id/FR-FCM-Z4KB) | Longitudinal data from one named patient. Adds time points, not a multi-donor cohort. |
| [Functional CAR-T atlas](https://github.com/ML4BM-Lab/Functional-cart-atlas) | Large donor/patient count, but scRNA-seq; not fluorescence-flow event data. Excluded from the flow-gating pool. |

## Consequence for the project

The best verified addition in this pass is a **28-patient processed fluorescence cohort**. A separate mass-cytometry archive exposes five patient-coded series. Neither should be represented as a new raw fluorescence manufacturing cohort. The original 159 parsed FCS files and their limited donor diversity retain their original status. Cross-study donor identities have not been globally reconciled, so no combined independent-donor total is asserted.

Prioritize the processed cohort for biological variation exploration, preserve the modality/stage boundaries, and resolve original FCS access for the 28-patient study or the raw-data candidates before claiming broad autogating validation. Source snapshots and selected-download manifests are under `data/discovery/`; detailed local results and downloaded data remain ignored by Git.
