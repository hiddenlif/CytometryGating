# Inspect donor identities in the deposited processed flow objects without
# executing author scripts or requiring the Seurat analysis package.
args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 3L) stop("Usage: inspect_processed_flow.R PRODUCT.rds PBMC.rds OUTPUT.json")
inspect <- function(path) {
  object <- readRDS(path)
  metadata <- attr(object, "meta.data")
  if (!is.data.frame(metadata) || !"patient" %in% names(metadata)) {
    stop("Expected a Seurat metadata data.frame with a patient column")
  }
  ids <- as.character(metadata$patient)
  if (anyNA(ids) || any(!nzchar(ids))) stop("Missing patient identifiers")
  assay <- attr(object, "assays")[["FACS"]]
  if (is.null(assay)) stop("No FACS assay present")
  features <- attr(attr(assay, "features"), "dimnames")[[1]]
  layers <- attr(assay, "layers")
  list(
    filename = basename(path), input_md5 = unname(tools::md5sum(path)),
    representation = "author-processed spectral flow; preselected live singlets and sketched cells",
    cells_in_object = nrow(metadata), unique_patients = length(unique(ids)),
    patient_ids = sort(unique(ids)), cells_per_patient = as.list(table(ids)),
    features = features, layers = names(layers),
    label_columns = names(metadata)[grepl("cluster|anno", names(metadata))]
  )
}
product <- inspect(args[[1]])
pbmc <- inspect(args[[2]])
all_ids <- sort(union(product$patient_ids, pbmc$patient_ids))
result <- list(
  product = product, pre_manufacturing_pbmc = pbmc,
  distinct_patient_ids_across_objects = length(all_ids),
  overlapping_patient_ids = length(intersect(product$patient_ids, pbmc$patient_ids)),
  additional_pbmc_only_patient_ids = setdiff(pbmc$patient_ids, product$patient_ids),
  limitation = paste("These are processed flow cell objects, not original FCS acquisitions.",
                     "Do not use them to validate debris, singlet, viability, unmixing, or original gate placement.",
                     "Existing author annotations are reference candidates, not independent expert ground truth.")
)
dir.create(dirname(args[[3]]), recursive = TRUE, showWarnings = FALSE)
jsonlite::write_json(result, args[[3]], pretty = TRUE, auto_unbox = TRUE, digits = NA)
cat("Product patients:", product$unique_patients, "\n")
cat("PBMC patients:", pbmc$unique_patients, "\n")
cat("Distinct patients across both objects:", length(all_ids), "\n")
