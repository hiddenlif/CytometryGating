---
name: cell-therapy-autogating
description: Inspect cell therapy FCS datasets and develop reviewable openCyto and FlowKit gating analyses for CAR-T process characterization, with panel, control, and reference-evidence checks.
---

# Cytometry gating

Use the companion repository to inspect FCS files and prepare reproducible analysis. Read [references/workflow.md](references/workflow.md) for commands and implementation limits. Locate the repository from `CELL_THERAPY_AUTOGATING_REPO`, or the current workspace when it contains this project's scripts and pyproject.toml. If unavailable, request its location or help install the companion repository.

## Intake before biological interpretation

Establish product modality, specimen type, manufacturing stage, intended populations, and marker-to-detector mapping. Distinguish specimens, controls, repeat acquisitions, exported subsets, and concatenations. Record unresolved donor/run identities instead of treating each file as independent.

Establish whether data are uncompensated, compensated, or spectrally unmixed, and identify relevant controls/matrices and transformations. A spillover keyword alone does not establish processing state. Do not compensate twice. Use controls and a documented assay strategy for positivity boundaries; density peaks alone do not establish CAR positivity or biological identity.

## Route by available evidence

- For intake, run the inventory and report parsing failures, channel schemas, and count units. A successful parse does not establish populations.
- For installation verification, run the openCyto / FlowKit FSC smoke test. Report an engineering gate-transfer check.
- For biological gating, identify a supported, expert-reviewed assay configuration. This draft repository has no validated biological configuration. If missing, prepare panel/control mapping and a proposed hierarchy for review; do not report unvalidated gates as established populations.
- For performance evaluation, require matched expert reference event membership or reproducible reference gates and an untouched evaluation split. Otherwise report exploratory results and missing evidence. Do not describe pseudo-reference labels as expert agreement.

Preserve biological shifts across stages. Adapt boundaries only under the documented method, recording adjustments and review flags. Avoid forcing population frequencies or expression distributions to match a reference sample.

## Deliverable

Report provenance, processing state, hierarchy/parameters, per-event membership, counts/percentages with named denominators, plots when biological gates are executed, versions, and failures requiring review. Separate execution, cross-tool agreement, expert agreement, and reviewer usefulness. Phenotype alone does not establish potency or product release suitability.
