# orc

Orchestrate the production, validation, and indexing of the YAML truth source
for [allometric/models v4](https://github.com/allometric/models).

`orc` walks a directory of model YAML files, validates each against a declared
schema, derives a stable 8-character content hash per model, and emits a flat
registry (one record per model) for downstream compilation to Arrow/Parquet.

## What it does

- **Validates** every publication YAML against a strict pydantic schema —
  unknown keys are rejected (`extra="forbid"`), so typos surface as validation
  errors instead of being silently absorbed.
- **Identifies** each model by a content-addressed 8-character hex id derived
  from the model's own canonical serialization: stable across reordering and
  reformatting, and a dedupe signal for content-identical models.
- **Emits** a flat registry (JSONL) and, optionally, three parquet tables
  (`publications`, `models`, `model_specs`) via DuckDB — no pyarrow dependency.

## Install

```sh
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

A virtual environment is required on Debian/Ubuntu, where system-wide
installs are blocked by PEP 668 (`externally-managed-environment`). The
editable install keeps `orc` in sync with this checkout; add `source .venv/bin/activate`
if you prefer activating the venv instead of calling `.venv/bin/orc` directly.

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

Add `--parquet dir` to also write the compiled records as three flat parquet
tables — `publications`, `models`, and `model_specs` — joined on
`pub_id` / `id` / `model_id`, using DuckDB as the writer (no pyarrow
dependency). Null-only columns stay properly typed, and empty tables still
produce a zero-row, correctly typed parquet file:

```sh
orc ingest --parquet out/
```

Warnings (e.g. content-identical models across publications) are printed but
do not fail the run.

## Documentation

- [Schema](schema.md) — the YAML file format, field by field
- [Model kinds](kinds.md) — `fixed_effects` vs `fixed_effects_set`, taxa, identifiers
- [Families](families.md) — curated model families, blobs, and invariants
- [API](api.md) — the `orc.ingest` entry points and CLI reference
