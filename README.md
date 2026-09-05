# orc

Orchestrate the production, validation, and indexing of the YAML truth source
for allometric/models. `orc` ingests publication and model family YAML files
and validates them against a declared schema. YAMLs are compiled into a set of
parquet files, used to distribute models in a queryable format.

Of paramount importance for model development are the publication and model
family schema specifications, which can be viewed at the documentation site
below.

Documentation: <https://allometric.org/orc/>

## Install

```sh
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

Activate the environment so `orc` is on your PATH:

```sh
source .venv/bin/activate
```

(Windows: `.venv\Scripts\activate`.) Verify the install:

```sh
orc --help
```

Once activated, `orc` runs from anywhere — no need to prefix `.venv/bin/`.
To leave the environment, run `deactivate`.

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
Add `--parquet dir` to also write the compiled records as six flat parquet
tables — `publications`, `models`, `model_specs`, and the family tables
`families`, `family_blobs`, `family_members` — joined on
`pub_id` / `id` / `set_id` / `model_id` / `family_id`, using DuckDB as the writer (no
pyarrow dependency). Null-only columns stay properly typed, and empty tables
still produce a zero-row, correctly typed parquet file:

```sh
orc ingest --parquet out/
```

Warnings (e.g. content-identical models across publications) are printed but
do not fail the run.

## More

- The YAML schema, model kinds, and identifier scheme are documented at
  <https://allometric.org/orc/> (`docs/` in this repo).
- `TODO.md` and `model_families_plan.md` track upcoming work.
