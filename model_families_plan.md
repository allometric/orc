# model_families_plan.md — curated model families

**Status: PLAN (not yet implemented).** This is the design document for a new
YAML schema (and, later, its compiled/queryable surface) that groups models
into curated, human-readable families. It is deliberately *less formal* than a
publication: a family is a labelled selection over the compiled registry, not a
source of new model content.

## Purpose

`publications`/`models`/`model_sets` are the *truth source* — they define what
models exist and their parameters. A **model family** is a curated grouping on
top of that truth: e.g. "published aboveground biomass equations for Pinus
resinosa," or "volume equations valid in the US North Central region."

Families let a researcher ask *"give me all models in this family"* and get a
coherent set back, without hand-maintaining a copy of those models. The family
does not store model content; it stores a **description plus a set of
selection rules** (model blobs) that resolve to actual models in the registry.

## File layout

- One YAML file per family, named by the family id, e.g.
  `model_families/<family_id>.yaml` (mirrors the one-file-per-publication
  convention).
- Family `id` is unique and acts as the primary key.
- Files live in a separate `model_families/` directory from `publications/`.

## Family-level fields

```yaml
family:
  id: pines_agb_resinosa        # unique family id (also the filename stem)
  title: "Aboveground biomass equations for Pinus resinosa"
  description: |
    A curated set of published aboveground biomass equations applicable to
    Pinus resinosa in the US North Central region. ~1 paragraph of context:
    what the family is, why it exists, any caveats about applicability.

model_blobs:
  - ...
```

- `family.id` — required, unique, filename stem.
- `family.title` — required, short human label.
- `family.description` — required, intended to be roughly one paragraph of
  context / applicability notes.
- `family.descriptors` — optional free-form metadata, if we later need it.

## Model blobs

A **model blob** is a selection rule that resolves to one or more concrete
models (rows in the compiled `model_specs`/`models` tables). Blobs are the
"parameters that structure queries": they filter the registry by pub id, model
set name, model id, taxa, region, component, etc.

Every blob in a family **must**:

1. resolve to models with the **same response variable**, and
2. resolve to models with the **same covariate requirements** (same set of
   covariates).

These two invariants make a blob (and the family) a coherent "apples to apples"
grouping — e.g. you never get a family that mixes volume-in-`ft3` with
biomass-in-`kg`, or mixes a dbh-only equation with a dbh+height equation.

### Blob structure (sketch)

A blob is expressed as a set of selection criteria:

```yaml
model_blobs:
  - label: "Resinosa biomass equations"
    response: mass              # invariant: must match across the family
    covariates: [dbh]           # invariant: must match across the family
    select:
      taxa:
        genus: Pinus
        species: resinosa
      region: [US-MN, US-WI]
  - label: "Red pine volume equations"
    response: volume
    covariates: [dsob]
    select:
      taxa:
        genus: Pinus
        species: resinosa
      descriptors: { equation_type: volume }
```

Intended `select` criteria (to be finalised):
- `pub_id` — a specific publication key.
- `model_id` — a specific 8-char content-hash id.
- `model_set_name` / `model_name` — a specific named model/set.
- `taxa` — filter by family/genus/species.
- `region`, `component` — scope filters.
- `descriptors` — arbitrary key/value filters on model descriptors.

### Semantics of a blob

- A blob is a **filter** over the compiled registry; it does not pin content.
  If the underlying registry changes, the blob re-resolves to whatever
  currently matches. (We may optionally allow *pinning* to specific `model_id`s
  for reproducibility — see Open questions.)
- Blob criteria are **ANDed** within a blob; multiple blobs in a family are
  **ORed** (a model belongs to the family if it matches any blob), provided the
  family-level invariants hold.
- The `response` / `covariates` invariants can be declared on each blob and/or
  hoisted to the family. When declared on the family, every blob must agree
  (validated).

## Validation rules (to implement in a `ModelFamily` schema)

- `family.id` unique and matches filename stem.
- `description` present (non-empty).
- At least one `model_blob`.
- Each blob has a `response` and `covariates`.
- Family-level `response`/`covariates` (if declared) match every blob.
- Blob `select` criteria use only known fields; unknown keys rejected
  (`extra="forbid"`, consistent with the rest of `orc`).
- Resolution check (in the compiled layer): every blob must actually resolve to
  ≥1 model, and the resolved models must satisfy the response/covariates
  invariants.

## Relationship to the storage layer

The family is a *view/selection* over the compiled `publications` / `models` /
`model_specs` tables. The compiled output should expose one row per
(model_family, model_spec) membership, e.g. a `model_family_members` table:

| column | type |
|---|---|
| `family_id` | string (FK → families) |
| `model_id` | string (FK → models) |
| `spec_index` | int (FK → model_specs) |
| `blob_label` | string (which blob selected it) |

This lets a consumer ask "all members of family X" via a join, reusing the
existing relational design rather than denormalising.

## Open questions

- Should a blob be allowed to *pin* specific `model_id`s for reproducibility,
  or stay a pure filter?
- How strictly to enforce the "same covariate requirements" invariant — exact
  set equality, or allow subset/superset?
- Do families need their own content hash / versioning, or are they purely
  named views?
- Should family membership rows be committed as an artifact (like parquet) or
  computed on demand?
- Where do families live in the repo layout and CI relative to publications?

## Out of scope (for now)

- The compiled/queryable family surface (parquet/duckdb membership table) —
  plan first, implement after the YAML schema is agreed.
- Any new model content; families only *reference* existing models.
