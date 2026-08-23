# Schema

Every publication is a single YAML file with `publication` (BibTeX metadata)
plus one or both of `models` (individual models) and `model_sets`
(parameterized families). The schema is declared in `orc/schema.py`; all
fields below are mandatory unless marked optional, and unknown keys are
rejected everywhere (`extra="forbid"`), so typos surface as validation errors
rather than being silently absorbed.

```yaml
publication:
  key: barnes_1962            # unique citation key
  bibtype: article            # one of the standard BibTeX types
  title: "..."
  author: "..."
  year: 1962                  # validated to a plausible range (1000-2100)
  journal: "..."              # optional BibTeX fields: journal, volume, pages,
                              # doi, url, publisher, institution, month, note,
                              # school, organization, series, booktitle, editor,
                              # edition, howpublished, number, address
  descriptors: {}             # optional free-form key/value metadata

models:
  - name: hstix50             # unique within the file
    type: fixed_effects       # required; extension point for future kinds
    id: a1b2c3d4              # optional 8-char hex; ingest cross-checks it
                              # against the derived content hash
    response: { hstix50: "ft" }   # {name: units}; compact map or object form
    covariates: { atb: "year" }   # {name: units-or-kind}; optional, default []
    prediction_function: "..."    # REQUIRED
    taxa: [{ genus: Quercus, species: alba }]   # optional
    region: [Oregon]          # optional
    component: stem           # optional
    covt_defs: { atb: "age at breast height" }   # optional definitions
    response_definition: "..."   # optional
    descriptors: {}           # optional
    description: "..."        # optional; human-readable prose on what the
                              # model/set is
    notes: "..."              # optional
    parameters: { a: 22.6, b: 0.5 }   # fixed_effects only

model_sets:
  - name: cuvol               # unique within the file
    type: fixed_effects_set   # required; extension point for future kinds
    response: { cuvol: "ft3" }
    covariates: { dsob: "in" }
    prediction_function: "b_1 + b_2 * dsob^2"   # REQUIRED
    taxa: [{ genus: Quercus, species: alba }]   # optional set-level scope
    region: [Oregon]          # optional set-level scope
    component: stem           # optional set-level scope
    descriptors: {}           # optional set-level scope
    specifications:           # one row per parameter combination
      - parameters: { b_1: 122.77, b_2: 0.4148 }
        taxa: [{ genus: Pinus, species: resinosa }]   # optional per-row scope
        region: [Oregon]      # optional per-row scope
        component: stem       # optional per-row scope
        descriptors: {}       # optional per-row scope
```

A complete worked example lives in
[`publications/hahn_1991.yaml`](https://github.com/allometric/orc/blob/main/publications/hahn_1991.yaml).

## Top-level rules

- `publication` is required.
- At least one of `models` or `model_sets` must be present (may be empty lists,
  but not both absent).
- Model and set `name` values must be unique within the file.
- `extra="forbid"` applies at every level: `publication`, models, sets,
  specification rows, and the nested `taxon` objects.

## `publication`

| Field        | Type              | Required | Notes                                   |
|--------------|-------------------|----------|-----------------------------------------|
| `key`        | string            | yes      | unique citation key                     |
| `bibtype`    | string            | yes      | one of the BibTeX types below           |
| `title`      | string            | yes      |                                         |
| `author`     | string            | yes      |                                         |
| `year`       | integer           | yes      | validated to 1000–2100                  |
| `journal`    | string            | no       |                                         |
| `volume`     | string or integer | no       |                                         |
| `pages`      | string            | no       |                                         |
| `doi`        | string            | no       |                                         |
| `url`        | string            | no       |                                         |
| `publisher`  | string            | no       |                                         |
| `institution`| string            | no       |                                         |
| `address`    | string            | no       |                                         |
| `month`      | string            | no       |                                         |
| `note`       | string            | no       |                                         |
| `school`     | string            | no       |                                         |
| `organization`| string           | no       |                                         |
| `series`     | string            | no       |                                         |
| `booktitle`  | string            | no       |                                         |
| `editor`     | string            | no       |                                         |
| `edition`    | string            | no       |                                         |
| `howpublished`| string           | no       |                                         |
| `number`     | string or integer | no       |                                         |
| `descriptors`| map               | no       | free-form key/value metadata            |

`bibtype` is one of the standard BibTeX types:
`article`, `book`, `booklet`, `inbook`, `incollection`, `inproceedings`,
`manual`, `mastersthesis`, `misc`, `phdthesis`, `proceedings`, `techreport`,
`unpublished`.

## Model entries (`models` / `model_sets`)

Shared fields (both kinds):

| Field                 | Type                    | Required | Notes                                   |
|-----------------------|-------------------------|----------|-----------------------------------------|
| `name`                | string                  | yes      | unique within the file                  |
| `type`                | string                  | yes      | `fixed_effects` or `fixed_effects_set`  |
| `prediction_function` | string                  | yes      |                                         |
| `response`            | map or object           | yes      | `{name: units}`; see below              |
| `covariates`          | map or list of objects  | no       | `{name: units-or-kind}`; default `[]`   |
| `taxa`                | list of `taxon`         | no       |                                         |
| `region`              | list of string          | no       |                                         |
| `component`           | string                  | no       |                                         |
| `covt_defs`           | map of string → string  | no       | covariate definitions                   |
| `response_definition` | string                  | no       |                                         |
| `descriptors`         | map                     | no       | free-form key/value metadata            |
| `description`         | string                  | no       | prose on what the model/set is          |
| `notes`               | string                  | no       |                                         |
| `id`                  | string                  | no       | `[0-9a-f]{8}`; see [Identifiers](kinds.md#identifiers) |

`response` and `covariates` accept either the compact map form
(`response: { hstix50: "ft" }`) or the object form
(`response: { name: hstix50, units: ft }`). Covariates may also be a list of
objects. In the compact map form, covariate values that are not units — e.g.
`{ atb: "year" }`, meaning "year" as a kind/definition — are preserved as-is;
`covt_defs` can then spell out the definition.

## `fixed_effects`

A single model with inline parameters:

| Field        | Type             | Required | Notes                          |
|--------------|------------------|----------|--------------------------------|
| `type`       | `fixed_effects`  | yes      |                                |
| `parameters` | map → float      | yes      | `{name: value}`                |

## `fixed_effects_set`

A parameterized family sharing one `prediction_function`:

| Field            | Type                   | Required | Notes                                 |
|------------------|------------------------|----------|---------------------------------------|
| `type`           | `fixed_effects_set`    | yes      |                                       |
| `specifications` | list of specification  | yes      | at least one row; see below           |

Each specification row is one parameter combination and may carry its own
optional `taxa`, `region`, `component`, and `descriptors` scope:

| Field        | Type             | Required | Notes                          |
|--------------|------------------|----------|--------------------------------|
| `parameters` | map → float      | yes      | `{name: value}`                |
| `taxa`       | list of `taxon`  | no       | per-row scope                  |
| `region`     | list of string   | no       | per-row scope                  |
| `component`  | string           | no       | per-row scope                  |
| `descriptors`| map              | no       | per-row scope                  |

!!! note "Parameter keys are derived from the rows"
    Every specification row must use **identical parameter keys** — this is
    validated. Parameter names are therefore derived from the rows, not
    declared separately.

## Validation summary

| Rule                                              | Enforced by                                        |
|---------------------------------------------------|----------------------------------------------------|
| Unknown keys rejected at every level              | `extra="forbid"` on every model                    |
| `year` within 1000–2100                           | `Publication._sane_year`                           |
| `id` matches `[0-9a-f]{8}`                        | `ModelBase._validate_id`                           |
| At least one of `models` / `model_sets`           | `ModelsFile._at_least_one_model_kind`              |
| Model and set names unique within file            | `ModelsFile._unique_model_names`                   |
| Set has at least one specification                | `FixedEffectsSetModel._consistent_parameter_keys`  |
| Identical parameter keys across all spec rows     | `FixedEffectsSetModel._consistent_parameter_keys`  |
| Ingested `id` matches derived content hash        | `ingest` (see [Identifiers](kinds.md#identifiers)) |
