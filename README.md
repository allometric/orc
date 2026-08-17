# orc

Orchestrate the production, validation, and indexing of the YAML truth source
for allometric/models v4.

`orc` walks a directory of model YAML files, validates each against a declared
schema, derives a stable 8-character content hash per model, and emits a flat
registry (one record per model) for downstream compilation to Arrow/Parquet.

## Schema

Every publication is a single YAML file with two top-level keys: `publication`
(BibTeX metadata) and `models` (one or more models). The schema is declared in
`orc/schema.py`; all fields below are mandatory unless marked optional, and
unknown keys are rejected everywhere (`extra="forbid"`), so typos surface as
validation errors rather than being silently absorbed.

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
  taxa:                       # optional; one or more taxon objects
    - family: Fagaceae
      genus: Quercus
  descriptors: {}             # optional free-form key/value metadata

models:
  - name: hstix50             # unique within the file
    type: fixed_effects       # discriminates the two model kinds
    id: a1b2c3d4              # optional 8-char hex; ingest cross-checks it
                              # against the derived content hash
    response: { hstix50: "ft" }   # {name: units}; compact map or object form
    covariates: { atb: "year" }   # {name: units-or-kind}; optional, default []
    taxa: [{ genus: Quercus, species: alba }]   # optional
    region: [Oregon]          # optional
    component: stem           # optional
    covt_defs: { atb: "age at breast height" }   # optional definitions
    response_definition: "..."   # optional
    descriptors: {}           # optional
    notes: "..."              # optional
    parameters: { a: 22.6, b: 0.5 }   # fixed_effects only
    equation: "a * atb^b"            # fixed_effects only
```

### Model kinds

The `type` field picks one of two structures:

- **`fixed_effects`** — a single model with inline `parameters` (a
  `{name: float}` map) and an `equation` string.
- **`fixed_effects_set`** — a parameterized family: `parameter_names`
  (the ordered list of parameter names) plus a `specifications` table, where
  each row holds a `{name: float}` `parameters` map and may carry its own
  optional `taxa`, `region`, `component`, and `descriptors`. `ingest`
  cross-checks every row against `parameter_names` and errors on any parameter
  not declared there.

### Taxon

`taxon` objects accept any subset of `family`, `genus`, `species`, but at least
one level must be present.

### Identifiers

Model `id` is optional in source. When present it must be an 8-character hex
string (`[0-9a-f]{8}`); `ingest` verifies it matches the model's content hash
and errors on mismatch. When absent, `ingest` derives and assigns the hash.

## Install

```sh
pip install .
```

## Usage

Point `orc ingest` at the models repo (or any directory of model YAML). With no
path it defaults to the current directory, so you can run it right inside the
allometric/models checkout:

```sh
cd path/to/allometric/models
orc ingest
```

Or be explicit:

```sh
orc ingest path/to/allometric/models/publications
orc ingest path/to/a/single.yaml
```

Exit code is `0` when every model validates, `1` if any errors are found.
Add `--registry out.jsonl` to also emit the compiled flat registry (one
JSON record per model) for downstream use:

```sh
orc ingest --registry registry.jsonl
```

Warnings (e.g. content-identical models across publications) are printed but
do not fail the run.
