# Project boundaries

This repository develops a cell therapy flow cytometry agent workflow. It is separate from prior interview examples, synthetic demonstrations, and benchmark tasks. Do not import their metrics or data as real scientific evidence.

Use manifest/checksum receipts for dataset claims. Report files, independent samples, donors, controls, and derivatives separately. Keep raw public data and detailed local reports out of Git. Do not commit credentials or private patient/product data.

The scatter smoke test is an engineering check, not validated biological analysis. Keep compensation/unmixing and transformations explicit; never compensate twice or infer marker mapping from channel position. Do not invent thresholds, product acceptance criteria, expert labels, or potency conclusions.

Run relevant integrity tests and real-FCS checks when changing parsing or gate transfer. All current inspected data is development-only. The separate FlowSOM repository remains deferred.
