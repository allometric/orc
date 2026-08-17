# orc

Orchestrate the production, validation, and indexing of the YAML truth source
for allometric/models v4.

`orc` walks a directory of model YAML files, validates each against a declared
schema, derives a stable 8-character content hash per model, and emits a flat
registry (one record per model) for downstream compilation to Arrow/Parquet.
