# Refit the engineering-only FSC-A gate independently per source FCS.
args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 2L) stop('Usage: opencyto_batch.R CASES.json OUTPUT.json')
source('scripts/opencyto_smoke.R')
cases <- jsonlite::fromJSON(args[[1]], simplifyVector = FALSE)
results <- lapply(cases, function(case) {
  tryCatch({
    run_smoke(case$input, case$output)
    list(input = case$input, output = case$output, status = 'fitted')
  }, error = function(e) list(input = case$input, output = case$output,
                             status = 'fit_failed', error = conditionMessage(e)))
})
jsonlite::write_json(results, args[[2]], pretty = TRUE, auto_unbox = TRUE)
