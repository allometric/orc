# Model families

!!! note "Status"
    The YAML schema is implemented (`orc.families`); resolution against the
    compiled registry, invariant checks, and the compiled membership table are
    planned next. The design doc is `model_families_plan.md`.

A **model family** is a curated grouping over the compiled registry — usually
a set of models where **each model corresponds to one species** (e.g. one
total stem volume equation per North Central US tree species, drawn from
multiple publications). A family stores **no model content**: it is a
description plus a set of selection rules (model blobs) that resolve to
concrete models in `publications` / `models` / `model_specs`. Families let a
researcher ask *"give me all models in this family"* and get a coherent set
back, without hand-maintaining a copy of those models.

Families are deliberately **loose**: the family itself declares no response or
covariate structure. Each blob carries its own `response` and `covariates`, so
a single family may group blobs with *different* structures (e.g. a volume
blob and a biomass blob) — the rigid "apples to apples" guarantee holds
*within* a blob, not across the family.

## File layout

- One YAML file per family, named by the family id:
  `model_families/<family_id>.yaml` (mirrors the one-file-per-publication
  convention).
- Family `id` is unique **globally** — across all families — and acts as the
  primary key. The id must also match the filename stem; both are checked by
  the ingest layer, which sees all files at once.

## Shape

```yaml
family:
  id: north_central_stem_volume  # unique family id (also the filename stem)
  title: "Stem volume equations for North Central US tree species"
  description: |
    A curated set of published total stem volume equations for tree species of
    the US North Central region. Each model corresponds to a single species.
  descriptors:
    country: US

model_blobs:
  - label: "Red pine (Pinus resinosa)"
    response: cuvol               # REQUIRED — response name for this blob
    covariates: [dsob]            # REQUIRED — covariate names for this blob
    select:
      taxa:
        genus: Pinus
        species: resinosa
  - label: "Jack pine (Pinus banksiana)"
    response: cuvol
    covariates: [dsob]
    select:
      taxa:
        genus: Pinus
        species: banksiana
  - label: "Sugar maple (Acer saccharum)"
    response: cuvol
    covariates: [dsob]
    select:
      taxa:
        genus: Acer
        species: saccharum
```

A complete loadable example lives in
[`model_families/north_central_stem_volume.yaml`](https://github.com/allometric/orc/blob/main/model_families/north_central_stem_volume.yaml).

## Family-level fields

| Field         | Type   | Required | Notes                                             |
|---------------|--------|----------|---------------------------------------------------|
| `id`          | string | yes      | globally unique; filename stem (ingest-time check)|
| `title`       | string | yes      | short human label                                 |
| `description` | string | yes      | non-empty; ~1 paragraph of context/applicability  |
| `descriptors` | map    | no       | free-form key/value metadata                      |

The family carries **no response/covariate structure** — that lives on each
blob (see below).

## Model blobs

A **model blob** is a selection rule that resolves to one or more concrete
models (rows in the compiled `model_specs` / `models` tables). It has an
optional `label` (provenance, appears in the membership table), a required
`response` and `covariates` (the structure its members must share), and a
required `select` (which models to consider).

| Field        | Type           | Required | Notes                                             |
|--------------|----------------|----------|---------------------------------------------------|
| `label`      | string         | no       | provenance label for the membership table         |
| `response`   | string         | yes      | response name for this blob's members             |
| `covariates` | list of string | yes      | covariate names; empty list allowed               |
| `select`     | `select` object| yes      | selection criteria; see below                     |

`response` / `covariates` are declared as bare names; resolution checks that
every model the blob resolves to agrees on the full (name, units) pairs — see
[Invariants](#invariants-per-blob).

### `select` criteria

| Field            | Type                    | Notes                                |
|------------------|-------------------------|--------------------------------------|
| `pub_id`         | string                  | a specific publication key           |
| `model_id`       | string                  | an 8-char content-hash id (`[0-9a-f]{8}`) |
| `model_set_name` | string                  | a specific named model set           |
| `model_name`     | string                  | a specific named model               |
| `taxa`           | `taxon` object          | partial filter; see below            |
| `region`         | list of string          | scope filter                         |
| `component`      | string                  | scope filter                         |
| `descriptors`    | map                     | arbitrary key/value filters          |

At least one criterion is required — an empty `select` would match every model
and is rejected. Unknown keys are rejected (`extra="forbid"`, consistent with
the rest of `orc`).

### Semantics

- Criteria are **ANDed** within a blob; multiple blobs in a family are
  **ORed** (a model belongs to the family if it matches any blob's select and
  structure).
- **Taxa matching:** a model/spec row matches `select.taxa` if **any** of its
  taxon entries satisfies *all* specified levels; levels not specified in the
  select do not filter. A row with
  `taxa: [{Pinus resinosa}, {Pinus strobus}]` matches a select on
  `{genus: Pinus, species: resinosa}`.
- A blob is a **filter** — it re-resolves as the registry changes. Pinning
  happens only in the compiled membership artifact.

## Invariants (per blob)

Every model resolved by a **single blob** must:

1. **Same response variable** — share the same *(name, units)* pair matching
   the blob's declared `response`. The blob declares the bare name (`cuvol`);
   resolution checks all its members agree on the full pair, so `cuvol` in
   `ft3` and `cuvol` in `m3` never mix.
2. **Same covariate requirements** — the **exact same set** of covariates,
   compared on *(name, units-or-kind)* pairs matching the blob's declared
   `covariates`. Exact set equality — subset and superset are not allowed
   (`dsob` in `in` vs `dsob` in `cm` are different; a dbh-only equation is not
   apples-to-apples with a dbh+height equation).

These are **enforced at resolution time, over the models each blob actually
resolves to** — a blob whose query resolves to volume when it declares
`response: mass` fails at resolve time. There is **no cross-blob constraint**:
different blobs in one family may declare different response/covariate
structures. This check is part of the planned ingest-layer work, not the
schema.

## Validation summary

Implemented in `orc.families` (schema level):

| Rule                                              | Enforced by                       |
|---------------------------------------------------|-----------------------------------|
| Unknown keys rejected at every level              | `extra="forbid"` on every model   |
| Blob `response`/`covariates` required; `description` required | required fields / `min_length` |
| At least one `model_blob`                         | `Field(min_length=1)`             |
| `select` has at least one criterion               | `FamilySelect._at_least_one_criterion` |
| `model_id` matches `[0-9a-f]{8}`                  | `FamilySelect._valid_model_id`    |
| `taxa` has at least one level                    | reused `Taxon` validation         |

Planned (ingest layer, sees all files and the compiled registry):

| Rule                                              | When                              |
|---------------------------------------------------|-----------------------------------|
| `family.id` globally unique                       | ingest                            |
| `family.id` matches filename stem                 | ingest                            |
| Every blob resolves to ≥1 model                   | resolve                           |
| Each blob's resolved models satisfy its invariants| resolve                           |

## API

```python
from orc.families import ModelFamily, FamilyMeta, ModelBlob, FamilySelect
from orc import ModelFamily  # also exported at package level
```

`ModelFamily` is the top-level model for a family YAML file; parse with
`ModelFamily.model_validate(yaml.safe_load(text))` exactly like
`ModelsFile`. See [API](api.md).
