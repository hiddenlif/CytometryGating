# Development roadmap

## First repository: openCyto + FlowKit

1. Establish environments, traceable downloads, FCS inventory, and a gate-transfer engineering check. Completed development checks are recorded in [TESTING.md](TESTING.md).
2. Reconcile HER2 CAR-T marker mapping, controls, compensation state, and condition metadata with the article. Obtain expert review where records are insufficient; do not manufacture reference labels.
3. Define one supported biological panel and hierarchy. Produce plots, per-event membership, counts, named denominators, and review flags.
4. Obtain expert-reviewed reference gates. Measure correction time, frequency bias, event agreement, and rare-population failure behavior. Separate engineering checks from biological validation.
5. Establish donor/run identities and an untouched evaluation cohort. Compare the same agent with/without the skill, and against a fixed-template baseline.
6. Data collection is paused at the user's direction. Any future expansion toward 500-1,000 well-described samples requires a new collection request. Count biological samples, donors, runs, files, controls, and derivatives separately.
7. Review code/data licenses and evidence before public publication. Development targets process characterization; release-test use requires separate assay-specific validation.

## Deferred second repository

**A separate FlowSOM repository is a user-requested future action item.** Potential scope: multidimensional cell therapy phenotyping, heterogeneity, or manufacturing-stage comparisons. Scope and implementation remain deferred. Do not add FlowSOM to the first repository's engine by default.
