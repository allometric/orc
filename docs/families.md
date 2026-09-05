---
title: Model families
description: The ORC model family schema and resolution rules.
---

# Model families

A model family is a curated set of models that share a common purpose or theme.
Examples include species-specific biomass modeling systems, site index
functions that cover a geograhpic region, or others. Model families are formed
by specifying a YAML file that describes the family and its member models,
which are partitioned into model blobs, sets of models with strict
response/covariate coherence. Models must be drawn from the compiled registry of
`allometric` models, which is itself formed from the [publication
files](/orc/publication/) that contain the actual model content. Hence, users must
often add the needed publications to form a family.

```yaml
family:
  id: doe_2024_growth_yield
  title: "Growth and yield models from Doe (2024)"
  description: |
    A curated family that groups the models published by Doe (2024): the
    western hemlock site index equation and the per-species stem volume
    equations. Each blob resolves to models in the `doe_2024` publication.
  maintainers:
    - name: "Jane Doe"
      email: jane.doe@example.com
      institution: "University of Washington"
      role: [aut, cre]
  descriptors:
    country: US

model_blobs:
  - id: hemlock_site_index
    label: "Western hemlock site index"
    response: hstix50
    covariates: [atb, hst]
    select:
      pub_id: doe_2024
      model_name: hstix50
  - id: red_pine_stem_volume
    label: "Red pine stem volume"
    response: cuvol
    covariates: [dsob]
    select:
      pub_id: doe_2024
      taxa:
        genus: Pinus
        species: resinosa
  - id: sugar_maple_stem_volume
    label: "Sugar maple stem volume"
    response: cuvol
    covariates: [dsob]
    select:
      pub_id: doe_2024
      taxa:
        genus: Acer
        species: saccharum
```

This family selects models from the hypothetical publication given in the
[Publication schema documentation](/orc/publication/): the `hstix50` model and
two `cuvol` specifications each resolve to rows in the `doe_2024` publication.

## `family`

This section contains metadata about the family itself. The `id` is a unique
identifier for the family, set as snake case but otherwise free-form. The
`title` is a short human-readable label, and the `description` is a non-empty
paragraph of context and applicability. The `maintainers` list names the
family's curators; authorship is tracked in the manner of R packages, with a
required `name` and optional contact metadata. The `descriptors` field is a
free-form map of key/value metadata that can be used for further specification
of the family.

| Field          | Type                | Required | Notes                                             |
|----------------|---------------------|----------|---------------------------------------------------|
| `id`           | string              | yes      | globally unique; filename stem (ingest-time check)|
| `title`        | string              | yes      | short human label                                 |
| `description`  | string              | yes      | non-empty; ~1 paragraph of context/applicability  |
| `maintainers`  | list of maintainer  | yes      | at least one; the family's curators               |
| `descriptors`  | map                 | no       | free-form key/value metadata                      |

### `maintainer`

| Field         | Type                      | Required | Notes                                        |
|---------------|---------------------------|----------|----------------------------------------------|
| `name`        | string                    | yes      | non-empty; maintainer's name                 |
| `email`       | string                    | no       | contact email                                |
| `orcid`       | string                    | no       | ORCID identifier                             |
| `institution` | string                    | no       | affiliation                                  |
| `role`        | string or list of string  | no       | `aut`, `cre`, `ctb`         |

`role` uses the standard CRAN role vocabulary: `aut` (author), `cre`
(creator/maintainer), `ctb` (contributor), `cph` (copyright holder), `fnd`
(funder), `rev` (reviewer), `ths` (thesis advisor), `trc` (translator).
Unknown roles are rejected.

Unknown keys are rejected (`extra="forbid"`, consistent with the rest of
`orc`).

The family carries **no response/covariate structure** — that lives on each
blob (see below).

## `model_blobs`

A model blob is, in essence, a selection rule that resolves to one or more
concrete models that share strict response and covariate structures. Each
blob leads with an `id` — a short name unique within the family — and may carry
a `label` (human-readable provenance, appears in the membership table), a
required `response` and `covariates` (the structure its members must share), and
a required `select` (which models to consider).

| Field        | Type           | Required | Notes                                             |
|--------------|----------------|----------|---------------------------------------------------|
| `id`         | string         | yes      | short name; unique within the family              |
| `label`      | string         | no       | provenance label for the membership table         |
| `response`   | string         | yes      | response name for this blob's members             |
| `covariates` | list of string | yes      | covariate names; empty list allowed               |
| `select`     | `select` object| yes      | selection criteria; see below                     |

`response` / `covariates` are declared as bare names; resolution checks that
every model the blob resolves to agrees on the full (name, units) pairs — see
[Blob Requirements](#blob-requirements).

### `select` criteria

| Field            | Type                    | Notes                                |
|------------------|-------------------------|--------------------------------------|
| `pub_id`         | string                  | a specific publication key           |
| `model_id`       | string                  | 8-char content-hash id (`[0-9a-f]{8}`) of a specific model — a spec row for sets, unique per model |
| `model_set_name` | string                  | a specific named model set           |
| `model_name`     | string                  | a specific named model               |
| `taxa`           | `taxon` object          | partial filter; see below            |
| `region`         | list of string          | scope filter                         |
| `component`      | string                  | scope filter                         |
| `descriptors`    | map                     | arbitrary key/value filters          |

At least one criterion is required — an empty `select` would match every model
and is rejected.

### Semantics

- Criteria are **ANDed** within a blob
- Models can belong to multiple blos within a family
- **Taxa matching:** a model/spec row matches `select.taxa` if **any** of its
  taxon entries satisfies *all* specified levels; levels not specified in the
  select do not filter. A row with
  `taxa: [{Pinus resinosa}, {Pinus strobus}]` matches a select on
  `{genus: Pinus, species: resinosa}`.

## Blob Requirements

Every model within a blob must share:

1. **The same response variable** — share the same *(name, units)* pair matching
   the blob's declared `response`. The blob declares the bare name (`cuvol`);
   resolution checks all its members agree on the full pair, so `cuvol` in
   `ft3` and `cuvol` in `m3` never mix.
2. **The same covariate requirements** — the **exact same set** of covariates,
   compared on *(name, units-or-kind)* pairs matching the blob's declared
   `covariates`. Exact set equality — subset and superset are not allowed
   (`dsob` in `in` vs `dsob` in `cm` are different; a dbh-only equation is not
   apples-to-apples with a dbh+height equation).

## Validation summary

Implemented in `orc.families` (schema level):

| Rule                                              | Enforced by                       |
|---------------------------------------------------|-----------------------------------|
| Unknown keys rejected at every level              | `extra="forbid"` on every model   |
| Blob `response`/`covariates` required; `description` required | required fields / `min_length` |
| Blob `id` required, lowercase snake_case          | `Field(pattern=...)`              |
| Blob `id` unique within the family                | `ModelFamily._unique_blob_ids`    |
| At least one `model_blob`                         | `Field(min_length=1)`             |
| At least one `maintainer`                         | `Field(min_length=1)`             |
| Maintainer `name` required                        | `Maintainer` model                |
| Maintainer `role` is a known CRAN role            | `Maintainer._valid_roles`         |
| `select` has at least one criterion               | `FamilySelect._at_least_one_criterion` |
| `model_id` matches `[0-9a-f]{8}`                  | `FamilySelect._valid_model_id`    |
| `taxa` has at least one level                    | reused `Taxon` validation         |

Implemented in `orc.ingest` (sees all files at once):

| Rule                                              | Enforced by                       |
|---------------------------------------------------|-----------------------------------|
| `family.id` globally unique                       | `orc.ingest`                      |
| `family.id` matches filename stem                 | `orc.ingest`                      |

## Resolving a family

`orc resolve` runs each blob's `select` criteria against the compiled registry
built from the publication files under a directory, and reports, per blob, the
models it resolves to — the debugging workflow for family development:

```sh
orc resolve model_families/doe_2024_growth_yield.yaml
```

```text
family: doe_2024_growth_yield

hemlock_site_index        "Western hemlock site index"
  -> hstix50 (doe_2024)                   response hstix50 [ft], covariates [atb, hst]
red_pine_stem_volume      "Red pine stem volume"
  -> cuvol spec Pinus resinosa (doe_2024) response cuvol [ft3], covariates [dsob]
sugar_maple_stem_volume   "Sugar maple stem volume"
  -> cuvol spec Acer saccharum (doe_2024) response cuvol [ft3], covariates [dsob]

3 blobs, 3 resolved models; invariants ok
```

The registry defaults to the current directory (the models repo); point it at
a different corpus with a second positional argument:

```sh
orc resolve model_families/doe_2024_growth_yield.yaml path/to/publications
```

Resolution enforces the per-blob invariants: every resolved model must share
the blob's `response` *(name, units)* pair and the exact `covariates`
*(name, units-or-kind)* set. A blob that resolves to no models, or to models
violating its declared structure, is an error and the command exits `1`.
Criteria are ANDed within a blob, and families are loose — blobs may declare
different response/covariate structures with no cross-blob constraint.

`orc ingest --parquet` runs the same resolution and **pins** the result: it
writes the family metadata to `families.parquet`, the blobs (with flattened
`select` criteria) to `family_blobs.parquet`, and one membership row per
resolved model to `family_members.parquet`, joined back to `model_specs` on
`model_id` (each row's unique model `id`, with `spec_index` for ordering).
This is the compiled membership artifact blobs resolve into; family YAML
files themselves store no model content.
