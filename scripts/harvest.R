#!/usr/bin/env Rscript
# One-off migration step 1 of 3: evaluate every R publication file with the
# installed `allometric` package and dump a neutral JSON intermediate.
#
# This is a THROWAWAY migration tool. It exists only to harvest the data
# locked inside the current R publication files; once allometric/models v4 is
# YAML-only, this file and convert.py are deleted (the `orc` package itself is
# the replacement, not the target of this script).
#
# Usage:
#   Rscript scripts/harvest.R <publications_dir> <parameters_dir> <out_dir>
#
# Why evaluate rather than parse: the publication files are arbitrary R that
# loops over parameter frames, constructs sets, and calls allometric's DSL.
# Reusing the installed, tested package to *evaluate* each file is far more
# faithful than writing an R-source parser that we then deprecate.
#
# The serializers below read the S4 slots directly rather than relying on
# allometric::publication_to_json(), which crashes on some real files (list
# columns, non-scalar citation fields).
#
# Requires R packages: allometric, jsonlite, tibble.

suppressMessages({
  library(allometric)
  library(jsonlite)
})

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 3) {
  stop("usage: Rscript scripts/harvest.R <publications_dir> <parameters_dir> <out_dir>")
}
pub_root <- args[[1]]
params_dir <- args[[2]]
out_dir <- args[[3]]
dir.create(out_dir, showWarnings = FALSE)

# Shadow the models-repo helper so parameter frames load from the given
# directory instead of a packaged install.
load_parameter_frame <- function(name) {
  tibble::as_tibble(
    read.csv(file.path(params_dir, paste0(name, ".csv")), na.strings = "")
  )
}

# `descriptors<-` is an unexported generic used by some publication files.
`descriptors<-` <- function(x, value) {
  x@descriptors <- tibble::as_tibble(value)
  x
}

.squish <- function(s) gsub("\\s+", " ", trimws(s))

.one <- function(v) {
  v <- unlist(v)
  if (length(v) == 0) NA_character_ else v[[1]]
}

unit_str <- function(x) {
  v <- unlist(x)
  if (length(v) == 0) {
    ""
  } else if (inherits(x, "units")) {
    as.character(units::deparse_unit(x))
  } else {
    as.character(v[[1]])
  }
}

fn_body_text <- function(fn) {
  expr <- body(fn)
  if (is.call(expr) && identical(expr[[1]], as.name("{"))) {
    stmts <- as.list(expr)[-1]
    lines <- vapply(stmts, function(s) .squish(paste(deparse(s), collapse = " ")), character(1))
    lines[lines != ""]
  } else {
    .squish(paste(deparse(expr), collapse = " "))
  }
}

cit_to_list <- function(cit) {
  optional <- c(
    "institution", "publisher", "journal", "volume", "number", "pages",
    "doi", "url", "address", "month", "note", "school", "organization",
    "series", "booktitle", "editor", "howpublished", "edition"
  )
  out <- list(
    key = .one(cit$key),
    bibtype = tolower(.one(cit$bibtype)),
    title = .one(cit$title),
    year = as.integer(.one(cit$year))
  )
  auth <- lapply(cit$author, function(a) {
    given <- unlist(a$given)
    paste(.one(a$family), paste(given, collapse = " "), sep = ", ")
  })
  out$author <- paste(auth, collapse = " and ")
  for (f in optional) {
    val <- suppressWarnings(cit[[f]])
    if (!is.null(val) && length(val) > 0) out[[f]] <- .one(val)
  }
  out
}

taxa_to_list <- function(taxa) {
  lapply(taxa, function(t) list(family = t@family, genus = t@genus, species = t@species))
}

desc_to_list <- function(df) {
  if (is.null(df) || ncol(df) == 0) return(list())
  out <- list()
  for (nm in colnames(df)) {
    v <- df[[nm]]
    if (length(v) == 0) next
    if (inherits(v[[1]], "Taxa")) {
      out[[nm]] <- taxa_to_list(v[[1]])
    } else if (is.list(v)) {
      out[[nm]] <- unlist(v)
    } else {
      out[[nm]] <- as.vector(v)
    }
  }
  out
}

model_to_list <- function(m) {
  resp <- m@response
  covt <- m@covariates
  params <- lapply(
    as.list(m@parameters),
    function(p) suppressWarnings(as.numeric(.one(p)))
  )
  list(
    response = list(name = names(resp)[[1]], unit = unit_str(resp[[1]])),
    covariates = Map(
      function(n, u) list(name = n, unit = unit_str(u)),
      names(covt), covt
    ),
    descriptors = desc_to_list(m@descriptors),
    parameters = params,
    prediction_function = paste(fn_body_text(m@predict_fn), collapse = "; "),
    covariate_definitions = if (length(m@covariate_definitions) > 0) {
      Map(
        function(n, d) list(name = n, definition = d),
        names(m@covariate_definitions), m@covariate_definitions
      )
    } else {
      list()
    },
    response_definition = if (!is.na(m@response_definition)) m@response_definition else ""
  )
}

run_pub <- function(file) {
  env <- new.env()
  sys.source(file, envir = env)
  for (o in rev(ls(env))) {
    if (inherits(get(o, env), "Publication")) return(get(o, env))
  }
  stop("no Publication object found")
}

files <- list.files(pub_root, pattern = "\\.R$", recursive = TRUE, full.names = TRUE)
if (length(files) == 0) stop("no .R files found under ", pub_root)

ok <- fail <- n_models <- 0
failed <- c()

for (f in files) {
  id <- tools::file_path_sans_ext(basename(f))
  pub <- tryCatch(run_pub(f), error = function(e) NULL)
  if (is.null(pub)) {
    fail <- fail + 1
    failed <- c(failed, id)
    next
  }
  out <- list(pub = list(key = pub@id, citation = cit_to_list(pub@citation)), models = list())
  for (i in seq_along(pub@response_sets)) {
    for (j in seq_along(pub@response_sets[[i]])) {
      for (m in pub@response_sets[[i]][[j]]@models) {
        out$models[[length(out$models) + 1]] <- model_to_list(m)
        n_models <- n_models + 1
      }
    }
  }
  writeLines(
    toJSON(out, auto_unbox = TRUE, digits = NA, pretty = TRUE),
    file.path(out_dir, paste0(id, ".json"))
  )
  ok <- ok + 1
}

cat(sprintf("harvested %d/%d publications, %d models\n", ok, ok + fail, n_models))
if (length(failed) > 0) {
  cat("failed:", paste(failed, collapse = ", "), "\n")
  quit(status = 1)
}