---
title: orc
description: Documentation for validating and indexing allometric model YAML.
---

`orc` orchestrates the production, validation, and indexing of the YAML truth
source for [allometric/models](https://github.com/allometric/models). This is
generally an internal package not intended for end users. Instead, it is used
by the GitHub actions in the `models` repository to ensure YAML files are
properly structured for further processing. Still, some documentation is useful
here, as `orc` contains the schema definitions for allometric models.

In sum, `orc`:

- **Validates** every publication YAML against a strict pydantic schema.
- **Identifies** each model by a content-addressed 8-character hex id derived
  from the model's own canonical serialization: stable across reordering and
  reformatting.
- **Emits** six flat parquet tables (`publications`, `models`, `model_specs`,
  `families`, `family_blobs`, `family_members`) via DuckDB — no pyarrow
  dependency. These parquet tables are used directly by the [allometric R
  package](https://github.com/allometric/allometric).

## Install

```sh
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

A virtual environment is required on Debian/Ubuntu, where system-wide installs
are blocked by PEP 668 (`externally-managed-environment`). The editable install
keeps `orc` in sync with this checkout; add `source .venv/bin/activate` if you
prefer activating the venv instead of calling `.venv/bin/orc` directly.

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

Exit code is `0` when every model validates, `1` if any errors are found. Add
`--parquet dir` to also write the compiled records as six flat parquet tables —
`publications`, `models`, `model_specs`, and the family tables `families`,
`family_blobs`, `family_members` — joined on `pub_id` / `id` / `set_id` /
`model_id` / `family_id`, using DuckDB as the writer (no pyarrow dependency).
Null-only columns stay properly typed, and empty tables still produce a
zero-row, correctly typed parquet file:

```sh
orc ingest --parquet out/
```

Warnings (e.g. content-identical models across publications) are printed but
do not fail the run.

## Documentation

- [Publication](/orc/publication/) — the YAML file format, field by field
- [Model kinds](/orc/kinds/) — `fixed_effects` vs `fixed_effects_set`, taxa, identifiers
- [Model Families](/orc/families/) — curated model families, blobs, and invariants
- [API](/orc/api/) — the `orc.ingest` entry points and CLI reference
