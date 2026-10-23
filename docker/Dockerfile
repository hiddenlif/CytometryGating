FROM bioconductor/bioconductor_docker:RELEASE_3_22@sha256:e34177896c1579f66d48b756e4229b58237499183a089da084af72d7aba1d40a
RUN Rscript -e 'BiocManager::install(c("openCyto", "flowCore", "flowWorkspace", "jsonlite"), ask=FALSE, update=FALSE, Ncpus=2)'
RUN Rscript -e 'stopifnot(all(vapply(c("openCyto", "flowCore", "flowWorkspace", "jsonlite"), requireNamespace, logical(1), quietly=TRUE))); write.table(installed.packages()[, c("Package", "Version")], "/opt/cytometry-packages.tsv", sep="\t", row.names=FALSE, quote=FALSE)'
WORKDIR /work
ENTRYPOINT ["Rscript"]
