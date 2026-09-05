---
title: Publication
description: The ORC publication YAML schema.
---

Publications are the primary way in which models enter into the `allometric`
ecosystem. Publications are represented as YAML files containing a metadata
field (`publication`) and one or more model entries (`models` or `model_sets`).
The following is an example of what a publication file might look like:

```yaml
publication:
  key: doe_2024
  bibtype: article
  title: "Growth and yield of a mixed conifer stand"
  author: "Doe, Jane"
  year: 2024
  descriptors:
    country: US

models:
  - name: hstix50
    type: fixed_effects
    response: { hstix50: "ft" }
    covariates: { atb: "year", hst: "ft" }
    taxa:
      - family: Pinaceae
        genus: Tsuga
        species: heterophylla
    parameters:
      a: 22.6
      b: 0.014482
      c: 0.001162
    prediction_function: "4.5 + a * exp((b - c * log(atb)) * (hst - 4.5))"
    description: "Site index equation; Table 1, eq. 1"

model_sets:
  - name: cuvol
    type: fixed_effects_set
    response: { cuvol: "ft3" }
    covariates: { dsob: "in" }
    prediction_function: "b_1 + b_2 * dsob^2"
    description: "Stem volume by species; Table 2, eqs. 4-5"
    specifications:
      - parameters: { b_1: 122.77, b_2: 0.4148 }
        taxa: [{ genus: Pinus, species: resinosa }]
      - parameters: { b_1: 0.25, b_2: 1.3 }
        taxa: [{ genus: Acer, species: saccharum }]
```

Each of the following sections specifies portions of the schema and its
possibilities. Note that a `publication` section is required, and at least one
of `models` or `model_sets` is required.

## `publication`

This section contains the bibliographic metadata for the publication. The `key`
is a unique identifier for the publication, codified typically as `author_year`
(e.g. `doe_2024`). The `bibtype` is one of the standard BibTeX types, and the
remaining fields are standard bibliographic fields. The `descriptors` field is a
free-form map of key/value metadata that can be used for further specification
of the publication.

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

## `models`

A set of individual allometric model, most useful when specifying one or a few
models. Each model has a `prediction_function` and a set of `parameters`, along
with a `response` and `covariates`.

| Field                 | Type                    | Required | Notes                                   |
|-----------------------|-------------------------|----------|-----------------------------------------|
| `name`                | string                  | yes      | unique within the file                  |
| `type`                | `fixed_effects`         | yes      |                                         |
| `prediction_function` | string                  | yes      |                                         |
| `response`            | map or object           | yes      | `{name: units}`; see below              |
| `covariates`          | map or list of objects  | no       | `{name: units-or-kind}`; default `[]`   |
| `parameters`          | map → float             | yes      | `{name: value}`                         |
| `taxa`                | list of `taxon`         | no       |                                         |
| `region`              | list of string          | no       |                                         |
| `component`           | string                  | no       |                                         |
| `covt_defs`           | map of string → string  | no       | covariate definitions                   |
| `response_definition` | string                  | no       |                                         |
| `descriptors`         | map                     | no       | free-form key/value metadata            |
| `description`         | string                  | no       | prose on what the model is              |
| `notes`               | string                  | no       |                                         |
| `id`                | string                  | no       | `[0-9a-f]{8}`; see [Identifiers](/orc/kinds/#identifiers) |

`response` and `covariates` accept either the compact map form
(`response: { hstix50: "ft" }`) or the object form
(`response: { name: hstix50, units: ft }`). Covariates may also be a list of
objects. In the compact map form, covariate values that are not units — e.g.
`{ atb: "year" }`, meaning "year" as a kind/definition — are preserved as-is;
`covt_defs` can then spell out the definition.

## `model_sets`

A set of models that share a `prediction_function`, `response`, and `covariates`
but differ in their `parameters`. Each row in the `specifications` list is one
parameter combination, as well as other identifying information such as `taxa`
etc.

| Field                 | Type                    | Required | Notes                                   |
|-----------------------|-------------------------|----------|-----------------------------------------|
| `name`                | string                  | yes      | unique within the file                  |
| `type`                | `fixed_effects_set`     | yes      |                                         |
| `prediction_function` | string                  | yes      |                                         |
| `response`            | map or object           | yes      | `{name: units}`; see the `models` section for accepted forms |
| `covariates`          | map or list of objects  | no       | `{name: units-or-kind}`; default `[]`   |
| `specifications`      | list of specification   | yes      | at least one row; see below             |
| `taxa`                | list of `taxon`         | no       |                                         |
| `region`              | list of string          | no       |                                         |
| `component`           | string                  | no       |                                         |
| `covt_defs`           | map of string → string  | no       | covariate definitions                   |
| `response_definition` | string                  | no       |                                         |
| `descriptors`         | map                     | no       | free-form key/value metadata            |
| `description`         | string                  | no       | prose on what the set is                |
| `notes`               | string                  | no       |                                         |
| `id`                | string                  | no       | `[0-9a-f]{8}`; see [Identifiers](/orc/kinds/#identifiers) |

Each specification row is one parameter combination and may carry its own
optional `taxa`, `region`, `component`, and `descriptors` scope:

| Field        | Type             | Required | Notes                          |
|--------------|------------------|----------|--------------------------------|
| `parameters` | map → float      | yes      | `{name: value}`                |
| `taxa`       | list of `taxon`  | no       | per-row scope                  |
| `region`     | list of string   | no       | per-row scope                  |
| `component`  | string           | no       | per-row scope                  |
| `descriptors`| map              | no       | per-row scope                  |

:::note[Parameter keys are derived from the rows]
Every specification row must use **identical parameter keys** — this is
validated. Parameter names are therefore derived from the rows, not
declared separately.
:::
