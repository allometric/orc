# API

The public surface is small: `orc.ingest` for the pipeline entry points,
`orc.schema` for the validated models, and `orc.ids` for content addressing.
Everything else (`orc.cli`, `orc.writer`) is internal.

## CLI

```
orc [--version] ingest [path] [--registry OUT.jsonl] [--parquet DIR]
```

| Flag         | Meaning                                                    |
|--------------|------------------------------------------------------------|
| `--version`  | print the installed version and exit                       |
| `path`       | YAML file or directory to ingest (default: `.`)           |
| `--registry` | write the compiled registry as JSONL to this path          |
| `--parquet`  | write `publications`/`models`/`model_specs` parquet tables to this directory |

Exit code is `0` when every model validates, `1` if any errors are found.

## `orc.ingest`

### `ingest(root: str | Path) -> IngestResult`

Ingest every YAML file under `root` (or the single file, if `root` is a file)
into a validated registry. Per file: parse YAML → validate against
`ModelsFile` → derive each model's 8-char content id (or cross-check one
already in source) → flatten to one `RegistryRecord` per model.

Never raises for schema problems; failures are collected on the result.
Returns `IngestResult`.

### `iter_yaml_files(root: str | Path) -> Iterator[Path]`

Yield candidate YAML files (`.yaml`, `.yml`) under `root`, in stable sorted
order. A single file yields itself.

### `load_models_file(path: Path) -> ModelsFile`

Parse and schema-validate a single model YAML file. Raises `yaml.YAMLError` or
`pydantic.ValidationError` on any failure, `ValueError` if the top level is
not a mapping.

### `model_id(model: Model) -> str`

Content-addressed id for one model, ignoring any `id` in source.

### `write_registry_jsonl(result: IngestResult, out: str | Path) -> None`

Dump the registry as newline-delimited JSON (one `RegistryRecord` per line).

### `IngestResult`

| Field      | Type                          | Meaning                                  |
|------------|-------------------------------|------------------------------------------|
| `registry` | `list[RegistryRecord]`        | one flat record per validated model      |
| `files`    | `list[tuple[Path, ModelsFile]]` | successfully ingested files            |
| `errors`   | `list[IngestError]`           | validation failures                      |
| `warnings` | `list[IngestWarning]`         | non-fatal notices (e.g. duplicate models)|

Property `ok` is `True` iff `errors` is empty.

### `IngestError` / `IngestWarning`

Dataclasses with `path` and `message` (plus optional `model_name` on errors);
`.render()` returns a human-readable one-line string.

## `orc.schema`

Pydantic v2 models. All use `extra="forbid"`.

| Model                  | Purpose                                            |
|------------------------|----------------------------------------------------|
| `ModelsFile`           | top-level structure of one publication YAML file   |
| `Publication`          | BibTeX metadata                                    |
| `Model`                | union: `FixedEffectsModel \| FixedEffectsSetModel` |
| `FixedEffectsModel`    | single model with inline `parameters`              |
| `FixedEffectsSetModel` | parameterized family with `specifications`         |
| `Specification`        | one row of a parameterized set                     |
| `Response`             | `{name, units}`                                    |
| `Covariate`            | `{name, units?}`                                   |
| `Taxon`                | `{family?, genus?, species?}`, at least one level  |
| `RegistryRecord`       | flat one-model-per-row view for the registry       |

`RegistryRecord` fields: `id`, `pub_id`, `pub_year`, `model_name`,
`model_type`, `response`, `covariates`, `parameters`, `prediction_function`,
`parameter_names`, `taxa`, `region`, `component`, `covt_defs`,
`response_definition`, `description`, `descriptors`, `source_file`.

## `orc.ids`

| Function        | Purpose                                                        |
|-----------------|----------------------------------------------------------------|
| `content_hash`  | first 8 hex chars of SHA-256 over `canonical_dump(obj)`        |
| `canonical_dump`| deterministic YAML serialization (sorted keys, normalized style)|
| `is_valid_id`   | `True` if a string matches `[0-9a-f]{8}`                        |
