# An engineering smoke test. This FSC density gate has no biological identity.
suppressPackageStartupMessages({library(openCyto); library(flowCore); library(flowWorkspace)})
run_smoke <- function(input, output) {
input <- normalizePath(input, mustWork = TRUE)
dir.create(output, recursive = TRUE, showWarnings = FALSE)
frame <- read.FCS(input, transformation = FALSE, truncate_max_range = FALSE)
if (!"FSC-A" %in% colnames(frame)) stop("Smoke test requires explicit FSC-A channel")
template_file <- file.path(output, "smoke-template.csv")
write.csv(data.frame(alias = "demo_fsc_high", pop = "+", parent = "root", dims = "FSC-A",
                     gating_method = "mindensity", gating_args = "", collapseDataForGating = FALSE,
                     groupBy = "", preprocessing_method = "", preprocessing_args = ""),
          template_file, row.names = FALSE)
gs <- GatingSet(flowSet(list(frame)))
template <- gatingTemplate(template_file)
gt_gating(template, gs)
gh <- gs[[1]]
members <- gh_pop_get_indices(gh, "demo_fsc_high")
gate <- gh_pop_get_gate(gh, "demo_fsc_high")
write.csv(data.frame(event_index_0 = seq_along(members) - 1L, member = as.integer(members)),
          file.path(output, "r-membership.csv"), row.names = FALSE)
threshold <- gate@min[[1]]
if (!is.finite(threshold)) stop("Expected a finite lower bound for the positive mindensity gate")
jsonlite::write_json(list(
  purpose = "engineering smoke test; not a cell identification or CAR positivity gate",
  input_filename = basename(input), channel = "FSC-A", lower_bound = threshold,
  input_md5 = unname(tools::md5sum(input)),
  upper_bound = if (is.finite(gate@max[[1]])) gate@max[[1]] else NULL,
  event_count = length(members), selected_count = sum(members),
  transformation = "none", compensation = "none; FSC only",
  openCyto = as.character(packageVersion("openCyto")),
  flowCore = as.character(packageVersion("flowCore")),
  flowWorkspace = as.character(packageVersion("flowWorkspace"))
), file.path(output, "r-gate.json"), pretty = TRUE, auto_unbox = TRUE, digits = NA, null = "null")
capture.output(sessionInfo(), file = file.path(output, "R-sessionInfo.txt"))
print(gs_pop_get_stats(gs))
}
if (sys.nframe() == 0L) {
  args <- commandArgs(trailingOnly = TRUE)
  if (length(args) != 2L) stop("Usage: opencyto_smoke.R INPUT.fcs OUTPUT_DIR")
  run_smoke(args[[1]], args[[2]])
}
