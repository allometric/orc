# orc

Orchestrate the production, validation, and indexing of the YAML truth source
for allometric/models. `orc` ingests publication and model family YAML files
and validates them against a declared schema. YAMLs are compiled into a set of
parquet files, used to distribute models in a queryable format.

Of paramount importance for model development are the publication and model
family schema specifications, which can be viewed at the documentation site
below.

Documentation: <https://allometric.github.io/orc/>

## Install

```sh
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

## Usage

`orc` is typically used when sitting inside a checkout of the allometric/models
repo, but it can also be run from any directory with a path to the models repo
or a single model YAML file.

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

## More

- The YAML schema, model kinds, and identifier scheme are documented at
  <https://allometric.github.io/orc/> (`docs/` in this repo).
- `TODO.md` and `model_families_plan.md` track upcoming work.
