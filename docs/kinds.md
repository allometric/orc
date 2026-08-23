# Model kinds

The top-level key picks the structure, and `type` (required on every entry) is
the extension point for future model kinds.

## `fixed_effects` (`models`)

A single model with inline `parameters` (a `{name: float}` map) plus the
shared `prediction_function` string:

```yaml
models:
  - name: hstix50
    type: fixed_effects
    response: { hstix50: "ft" }
    covariates: { atb: "year" }
    prediction_function: "a * hstix50^b"
    parameters: { a: 22.6, b: 0.5 }
```

## `fixed_effects_set` (`model_sets`)

A parameterized family: a `specifications` table, where each row holds a
`{name: float}` `parameters` map and may carry its own optional `taxa`,
`region`, `component`, and `descriptors`. The set shares a single
`prediction_function`:

```yaml
model_sets:
  - name: cuvol
    type: fixed_effects_set
    response: { cuvol: "ft3" }
    covariates: { dsob: "in" }
    prediction_function: "b_1 + b_2 * dsob^2 + b_3 * dsob^3"
    specifications:
      - parameters: { b_1: 122.77, b_2: 0.4148, b_3: -2.397e-05 }
        taxa: [{ genus: Pinus, species: resinosa }]
      - parameters: { b_1: 0.25, b_2: 1.3, b_3: -0.001 }
        taxa: [{ genus: Acer, species: saccharum }]
```

Every specification row must use identical parameter keys (validated);
parameter names are therefore derived from the rows, not declared separately.

## Taxon

`taxon` objects accept any subset of `family`, `genus`, `species`, but at least
one level must be present:

```yaml
taxa:
  - genus: Quercus
    species: alba
  - family: Pinaceae
```

## Identifiers

Every model in the registry is identified by an 8-character hex digest of its
own canonical YAML representation (`[0-9a-f]{8}`, e.g. `a1b2c3d4`). The id is
derived from content, not stored position, so it is:

- **stable** across reordering / reformatting of the source file — the hash is
  over a canonical dump (`sort_keys`, flow style and quoting normalized), not
  raw bytes;
- **content-addressed** — edit any parameter and the id changes, which is what
  lets a model family pin to exact model versions.

Hashing the model's *own* serialized content (rather than the whole file)
means a change to an unrelated model in the same file does not re-id this
model, and identical models across publications collapse to the same id — a
dedupe signal the assembly layer can use. `orc ingest` prints a warning when it
finds content-identical models across publications.

### In source files

Model `id` is optional in source. When present it must be an 8-character hex
string; `ingest` verifies it matches the model's content hash and errors on
mismatch. When absent, `ingest` derives and assigns the hash.

### In the registry

The compiled registry (`--registry` / parquet) carries the derived id per
record as `id`, plus `pub_id` (the publication `key`) and `model_name`; parquet
tables join on `pub_id` / `id` / `model_id`.
