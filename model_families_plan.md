# model_families_plan.md — curated model families

**Status: PARTIALLY IMPLEMENTED.** The `ModelFamily` YAML schema (families,
blobs, select criteria) is implemented in `orc/families.py` — see
[docs/families.md](docs/families.md). Pending: resolution against the compiled
registry, invariant checks, the compiled `model_family_members` table, and the
`orc ingest` integration. This document remains the design reference for the
pending parts.

## Purpose

`publications`/`models`/`model_sets` are the *truth source* — they define what
models exist and their parameters. A **model family** is a curated grouping on
top of that truth: usually a set of models where **each model corresponds to
one species** (e.g. one total stem volume equation per North Central US tree
species, drawn from multiple publications).

Families let a researcher ask *"give me all models in this family"* and get a
coherent set back, without hand-maintaining a copy of those models. The family
does not store model content; it stores a **description plus a set of
selection rules** (model blobs) that resolve to actual models in the registry.

Families are deliberately **loose**: the family declares no response or
covariate structure. Each blob carries its own `response` and `covariates`, so
a single family may group blobs with *different* structures (e.g. a volume
blob and a biomass blob). The rigid "apples to apples" guarantee holds
*within* a blob — a blob never mixes volume-in-`ft3` with biomass-in-`kg`, or
dbh-only equations with dbh+height equations — but there is **no cross-blob
constraint**.

## File layout

- One YAML file per family, named by the family id, e.g.
  `model_families/<family_id>.yaml` (mirrors the one-file-per-publication
  convention).
- Family `id` is unique **globally** — across all families, not just within
  the `model_families/` directory — and acts as the primary key.
- Files live in a separate `model_families/` directory from `publications/`.

## Family-level fields

```yaml
family:
  id: north_central_stem_volume # unique family id (also the filename stem)
  title: "Stem volume equations for North Central US tree species"
  description: |
    A curated set of published total stem volume equations for tree species of
    the US North Central region. Each model corresponds to a single species.
  descriptors: {}               # optional free-form metadata

model_blobs:
  - ...
```

- `family.id` — required, globally unique, filename stem.
- `family.title` — required, short human label.
- `family.description` — required, intended to be roughly one paragraph of
  context / applicability notes.
- `family.descriptors` — optional free-form metadata.

The family carries **no response/covariate structure** — that lives on each
blob (see below), which is what keeps families loose.

## Model blobs

A **model blob** is a selection rule that resolves to one or more concrete
models (rows in the compiled `model_specs`/`models` tables). Blobs are the
"parameters that structure queries": each blob declares the response and
covariate structure its members must share, and filters the registry by pub
id, model set name, model id, taxa, region, component, etc.

### Blob structure

```yaml
model_blobs:
  - label: "Red pine (Pinus resinosa)"
    response: cuvol              # REQUIRED — response name for this blob
    covariates: [dsob]           # REQUIRED — covariate names for this blob
    select:
      taxa:
        genus: Pinus
        species: resinosa
  - label: "Sugar maple (Acer saccharum)"
    response: cuvol
    covariates: [dsob]
    select:
      taxa:
        genus: Acer
        species: saccharum
```

Blob fields:
- `label` — optional, provenance label that appears in the membership table.
- `response` — required, the response name for this blob's members.
- `covariates` — required, the covariate names for this blob's members (empty
  list allowed for covariate-free models).
- `select` — required, the selection criteria.

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
  currently matches. (Pinning happens only in the compiled membership
  artifact — see [Storage layer](#relationship-to-the-storage-layer).)
- A model belongs to a blob if it matches the blob's `select` **and** agrees
  with the blob's `response` / `covariates` (see [Invariants](#invariants)).
  Criteria are **ANDed** within a blob; multiple blobs in a family are
  **ORed**.
- **Taxa matching rule:** a model/spec row matches `select.taxa` if **any** of
  its taxon entries satisfies *all* specified levels; levels not specified in
  the select do not filter. A row with `taxa: [{Pinus resinosa}, {Pinus
  strobus}]` therefore matches a select on `{genus: Pinus, species: resinosa}`.

## Invariants (per blob)

Every model resolved by a **single blob** must:

1. **Same response variable** — share the same *(name, units)* pair matching
   the blob's declared `response`. Comparison is on the pair, not the bare
   name: `cuvol` in `ft3` and `cuvol` in `m3` are different responses, and a
   name-only check would silently mix them.
2. **Same covariate requirements** — the **exact same set** of covariates,
   compared on *(name, units-or-kind)* pairs matching the blob's declared
   `covariates`. `dsob` in `in` and `dsob` in `cm` are different covariates.
   Exact set equality — subset/superset is **not** allowed (a dbh-only
   equation is not apples-to-apples with a dbh+height equation).

These invariants are **enforced at resolution time, over the models each blob
actually resolves to** — not over declarations. A blob whose query resolves to
volume when it declares `response: mass` fails at resolve time. There is **no
cross-blob constraint**: different blobs in one family may declare different
response/covariate structures.

## Resolution

- Families resolve over the compiled registry: `model_specs` rows joined with
  `models` and `publications`.
- **Set-level hashing:** `model_id` hashes a whole `model_sets` entry (all its
  specifications), so `model_id` pins the *set*, not one row. Pinning an
  individual spec row therefore requires the `(model_id, spec_index)` pair.
- **Membership — keep all:** every (family, spec row, matching blob)
  combination produces one membership row. A spec row matching multiple blobs
  yields multiple rows (blob provenance is useful); the "all members of family
  X" query dedupes on (family, model_id, spec_index).
- Compiled membership rows pin the model ids at compile time (a snapshot). The
  family YAML itself stays a pure filter that re-resolves.

## Validation rules (implemented in the `ModelFamily` schema)

- `family.id` globally unique and matches the filename stem (ingest-time
  checks; the schema enforces non-empty).
- `family.title` and `family.description` present; description non-empty.
- At least one `model_blob`.
- Each blob has `response` and `covariates` (required).
- Blob `select` criteria use only known fields; unknown keys rejected
  (`extra="forbid"`, consistent with the rest of `orc`).
- `select` has at least one criterion; `model_id` is an 8-char hex string;
  `taxa` has at least one level.
- Resolution checks (ingest time, over the compiled registry):
  - every blob must resolve to ≥1 model, and
  - each blob's resolved models must satisfy that blob's invariants.

## Relationship to the storage layer

The family is a *view/selection* over the compiled `publications` / `models` /
`model_specs` tables. The compiled output should expose one row per
(model_family, model_spec, blob) membership, e.g. a `model_family_members`
table:

| column | type |
|---|---|
| `family_id` | string (FK → families) |
| `model_id` | string (FK → models; pins the set) |
| `spec_index` | int (FK → model_specs; pins the row) |
| `blob_label` | string (which blob selected it) |

This lets a consumer ask "all members of family X" via a join, reusing the
existing relational design rather than denormalising. Membership rows are
computed at ingest time and emitted as an artifact (parquet) alongside
`publications` / `models` / `model_specs`; they are a snapshot, pinned to the
model ids that resolved.

Families get their own **definitional content hash** over the family YAML
(consistent with orc's content addressing). It versions the *definition*, not
the membership — membership is derived from the registry at compile time.

## CLI / CI

- `orc ingest` also walks `model_families/` when present: schema-validate each
  family, then resolve it against the compiled registry, erroring on any blob
  that resolves to zero models or on invariant violations. `--parquet` emits
  `model_family_members` alongside the existing three tables. One entry point,
  matching existing UX.
- Families live in `model_families/` beside `publications/` in the models
  repo.

## Decisions (locked)

- Response/covariate structure is declared **per blob**; families are loose —
  **no cross-blob structure constraint**.
- Invariants compare **(name, units)** pairs; covariate sets compared by
  **exact set equality** on (name, units-or-kind) pairs — enforced per blob
  over resolved models.
- **Keep-all** membership rows (one per matching blob); query-time dedupe.
- Family ids are **unique globally**.
- Family YAML is a **pure filter**; compiled membership is a **snapshot**
  pinned by model ids.
- Pinning a spec row requires **(model_id, spec_index)** — `model_id` alone
  pins the whole set.
- Taxa select: **any-entry match**; unspecified levels don't filter.
- Families carry **definitional content hashes**; membership is derived.
- `orc ingest` is the single entry point; `model_family_members` is emitted
  with `--parquet`.

## Out of scope (for now)

- The compiled/queryable family surface beyond the membership table —
  plan first, implement after the YAML schema is agreed.
- Any new model content; families only *reference* existing models.
