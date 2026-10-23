# Public dataset catalog

Checked on 2026-10-18. Counts come from version-bound repository inventories. Download and parse receipts are separate from discoverability.

| ID | Dataset | FCS files | Current role and limits |
|---|---|---:|---|
| `her2-car-t` | [HER2 CAR-T KnockIn in T cells](https://figshare.com/articles/dataset/HER2_CAR-T_KnockIn_in_T_cells/28824383), article 28824383, version 2 | 76 | Primary human T-cell engineering, Protein L readout, varied conditions. Source reports one donor shared with GFP knock-in. Biological sample count/control mapping unresolved. No author workspace in this deposit. |
| `t-cell-gfp-knockin` | [GFP CSS DNA Knock-In in T cells](https://figshare.com/articles/dataset/GFP_CSS_DNA_Knock-In_in_T_cells/28817957), version 1 | 67 | Adjacent primary T-cell engineering assay. GFP reporter data must not be relabeled as CAR-expression data. |
| `treg-characterization` | [Characterization of Regulatory T cells](https://figshare.com/articles/dataset/Characterization_of_Regulatory_T_cells/28817822), version 1 | 8 | One named stained acquisition, one unstained acquisition, six named compensation controls. This does not establish eight biological samples. |
| `car-nk-knockin` | [CAR knock-in in primary human NK cells](https://data.mendeley.com/datasets/4cwny84gs2/1), version 1, DOI 10.17632/4cwny84gs2.1 | 14 | Separate CAR-NK exploratory cohort. Three named exported subsets and one concatenation are excluded from independent-acquisition claims. Includes four FlowJo workspaces and one README. Donor counts are unverified. |

All four deposits list **CC BY 4.0**. Preserve contributor attribution and dataset DOI when reusing data. The software license does not replace these licenses. Contributor records and exact URLs are retained in source JSON snapshots under `data/manifests/`. All current files are development-only; no evaluation set has been claimed.

The first three deposits are associated with [Miniaturized scalable arrayed CRISPR screening in primary cells enables discovery at the single donor resolution](https://pmc.ncbi.nlm.nih.gov/articles/PMC12339676/). Its methods, under "Primary human T cell procurement and isolation," report one leukopak donor for the knock-in experiments, shared across the CAR and GFP knock-in experiments, and one regulatory T-cell donor for the Treg experiment. Thus these three deposits represent **two source-reported donor groups**, not 151 donors. File-level specimen/control relationships still require reconciliation. The NK donor count remains unresolved.

These are related experiments, not independent external validation cohorts. Reconcile methods with deposited files before assigning conditions or reference labels. The deposit includes filenames/doses not completely enumerated in the narrative protocol.

## Counting rules

- Cataloged FCS file: a repository entry ending in `.fcs`.
- Downloaded file: present locally and verified against source checksum and byte size.
- Distinct ordered event matrix: fingerprint of parsed event array, dimensions, and detector order. Detects exact event-data duplication, not all duplicates or subsets.
- Biological sample: documented donor/specimen, collection time, manufacturing run/stage, and condition. Panels, controls, exports, or repeat acquisitions may share the same biological sample.
- Independent donor: documented donor identifier. Never infer it from a well ID, event count, or distinct checksum.

Donor and sample identifiers remain null where unverified. Keep related donors, runs, controls, and derivatives together in future splits. Unknown identities cannot support donor-independent performance claims.

## Additional leads, excluded from the available pool

- [ElastiGate CAR-T QC study](https://www.nature.com/articles/s41598-025-99118-1): reports 19 leukapheresis and six final-product samples, 75 files including controls/replicates, and 71 target files after training selection. Download access/reference annotations unverified; do not add these to the downloaded pool or assume 25 donors.
- [High-dimensional temporal mapping of CAR T cells during manufacturing](https://pmc.ncbi.nlm.nih.gov/articles/PMC12126796/): datasets available from the corresponding author upon reasonable request. Relevant reference, not a verified public FCS download. No author has been contacted.
- [MCP_MassCytometry_ADHM2024, FR-FCM-Z76E](https://flowrepository.org/id/FR-FCM-Z76E): CAR-T manufacturing mass cytometry lead. Different modality, file count/access unverified, excluded from this fluorescence pool.

This inventory does not establish a 500-1,000 independent-sample cell therapy dataset. Additional documented donors/runs and expert annotation are needed.

See [the donor-focused follow-up](DONOR-DISCOVERY-2026-10-18.md) for new multi-patient processed flow data and separately tracked raw-data leads. It preserves these original counts and distinguishes each representation's validation limits.
