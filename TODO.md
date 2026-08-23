# orc TODO — compiled storage layer

Handoff notes for the next session. Implements the storage plan in
`allometric/models/storage.md` (parquet/duckdb output from the YAML truth
source). The goal is a queryable, committed artifact that replaces the old
`models.RDS` data surface.

## Current state

- `schema.py` — pydantic models: `ModelsFile` → `Publication` + `Model`
  (`FixedEffectsModel` | `FixedEffectsSetModel`). `extra="forbid"`, content hash
  `id` optional in source.
- `ingest.py` — walks `publications/`, validates, assigns content-hash ids,
  flattens each model into a `RegistryRecord` (one per *model*), dumps JSONL.
- `records.py` — canonical Layer-A records (`PublicationRecord`,
  `ModelRecord`, `ModelSpecRecord`) with set→spec fallback resolution.
- `writer.py` — flattens `ModelsFile`s and writes three parquet tables
  (`publications`, `models`, `model_specs`) via DuckDB's parquet writer, with
  explicit per-column type maps (null columns stay typed, empty tables yield
  zero-row typed files).
- `ids.py` — 8-char SHA-256 of canonical YAML dump; hash is per *model* (the
  whole set, not per spec).
- `cli.py` — `orc ingest [path] [--parquet DIR]`.
- Dependencies: `PyYAML`, `pydantic`, `duckdb` (writer only; no pyarrow).

## The three gaps (from storage.md)

1. **`fixed_effects_set` is not flattened.** `ingest` collapses a set into one
   record with `parameter_names` from the first spec; the actual per-spec
   parameter rows (and their own `taxa`/`region`/`component`/`descriptors`) are
   dropped. A queryable table needs one row per spec.
2. **Publication metadata is dropped.** `RegistryRecord` keeps only `pub_id` /
   `pub_year`; title/author/journal/doi/etc. live on `Publication` and are lost
   in the flat output.
3. **No writer and no CI.** Output stops at JSONL; nothing emits parquet/duckdb,
   and there's no action rebuilding the committed artifact.

## Proposed changes

### 1. `orc/records.py` (new) — canonical Layer A records

Define dataclasses (or pydantic models) for three tables, format-agnostic:

- `ModelRecord` — one row per model set/single model: `id`, `pub_id`,
  `model_name`, `model_type`, `response_name`, `response_units`,
  `covariates` (list of `{name, units}`), `prediction_function`, `covt_defs`,
  `response_definition`, `description`, `notes`, model-level `taxa`/`region`/
  `component`/`descriptors`, `source_file`.
- `ModelSpecRecord` — one row per *spec*: `id` (FK → model), `spec_index`
  (0 for single models, ordinal in set), `parameters` (map), and per-spec
  `taxa`/`region`/`component`/`descriptors` with fallback to the model-level
  values when the spec doesn't declare its own.
- `PublicationRecord` — all `Publication` BibTeX fields + `key`.

Flattening rule (from storage.md): a `fixed_effects` model yields one spec row
(spec_index 0); a `fixed_effects_set` yields one row per `specifications` entry.
Keep the existing content hash at the *set* granularity and use `spec_index` to
disambiguate rows within a set.

### 2. Extend `orc/ingest.py`

Build the three record lists from a validated `ModelsFile`/registry, in
addition to (or replacing) the current lossy `RegistryRecord` path. The JSONL
registry writer (`--registry` / `write_registry_jsonl`) has been removed;
`RegistryRecord` remains as the in-memory registry until this supersedes it.

### 3. `orc/parquet.py` (new) — writer

Write `models.parquet`, `model_specs.parquet`, `publications.parquet` via
`pyarrow`. Nested types for taxa/covariates/region/parameters (do **not**
pivot lists into comma-joined strings — the R consumer filters over list
columns). Deterministic ordering (sort by `id`, then `spec_index`); no
timestamps.

### 4. `orc/duckdb.py` (new) — optional writer

Write `publications.duckdb` with the three tables (or a wrapper that
`CREATE VIEW`s over the parquet files). Only if we decide to publish the
`.duckdb` artifact.

### 5. `orc/cli.py`

Add subcommands, e.g. `orc build-parquet <path> --out <dir>` and optionally
`orc build-duckdb <path> --out <file>`.

### 6. `pyproject.toml`

Add `pyarrow` (and `duckdb` if the wrapper is built) to dependencies /
optional `build` extra.

## Tests

- Round-trip a fixture through the new writers and query it back
  (`pyarrow` / `duckdb`) to confirm the flattening is lossless.
- `fixed_effects_set` → correct number of spec rows, correct `spec_index`,
  taxa/region/descriptors fallback behavior.
- Determinism: rebuild with no source change produces byte-identical output.

## Open questions (from storage.md, to confirm during implementation)

- Keep the content hash at the set level with `spec_index` disambiguation (as
  proposed), or introduce a per-spec hash?
- Should single `fixed_effects` models also appear in the spec table (one row)
  so consumers query one table, or be distinguished by `model_type`? (Recommend:
  single uniform table, `model_type` retained as a column.)
- Publish parquet only, or parquet + duckdb wrapper?
- `descriptors` allows `Scalar | list` values — how to type a mixed column
  (likely `VARCHAR`/JSON).

## Out of scope here

- `models/storage.md` already documents the repo layout, GitHub action, and
  downstream `allometric/allometric` consumer changes. Reference it rather than
  duplicating.

## Decision record: pub-level descriptor propagation (return to later)

**Status: DECIDED (pending implementation), recommendation only.**

Question: should publication-level `descriptors` propagate "down" into model /
model-set flat records so consumers don't have to join the publications table?

**Recommendation — Option 3: labeled denormalization.**

- **Never merge in the source schema.** A model's `descriptors` means *only*
  that model's descriptors. Keep the YAML declarative and honest; no implicit
  propagation from `publication`.
- **Merge, if at all, only in the flat-file writer**, and only as a widening —
  write `pub_descriptors` and `descriptors` as two separate fields per record.
  No join needed by consumers, and *no merge semantics exist* because nothing
  is combined.
- **Do not** use "model overrides pub" (write-over) — silent data loss, can't
  tell an intentional model-level value from a stale one.
- **Do not** invent a merge/override order rule unless a consumer genuinely
  needs a single dict; if we ever do, make it explicit and deterministic
  (model-level wins on key collision) and document it loudly.

Why: keeps propagation a writer/consumer concern rather than re-introducing
schema-level coupling (the same coupling we removed by dropping pub-level
`taxa`). Conflict detection is unnecessary by construction when scopes stay
separate.

**Update (superseded by relational design):** the decision to add
`pub_descriptors` widened onto model rows is now **moot**. With the three-table
relational layout (`publications` / `models` / `model_specs`) and consumers
joining, pub descriptors live on `publications` and model descriptors on
`models` — scopes stay separate with no denormalization at all. No widening is
needed. (Same outcome as Option 3, achieved structurally rather than by
widening.)

## Decision record: flat vs nested pub/models layout (return to later)

**Status: DECIDED — keep flat (siblings, not nested).**

Question: models/model_sets conceptually *belong to* a publication, but they
are top-level siblings of `publication` rather than nested under it. Is that a
problem?

Recommendation — keep the current flat layout:
- Ownership is already expressed by the file itself (one YAML file == one
  publication) plus `publication.key` as the join key. Nesting adds no
  information.
- Keeps `publication` a thin, well-typed BibTeX citation object, cleanly
  separated from model content. Nesting would make `Publication` a double-duty
  citation-and-container type and harder to reuse.
- Multiple top-level keys are normal YAML; no technical awkwardness.
- Content hash is per-model, independent of file layout, so nesting changes
  nothing there.

Revisit only if we ever support multiple publications per file.

## Decision record: record/table schema (fleshing out the database)

**Status: DECIDED — `orc/records.py` implemented.**

Three relational tables, format-agnostic, with consumers expected to *join*:

1. **`publications`** — one row / pub (`PublicationRecord`): pub_id (PK = key),
   all BibTeX fields, pub-level `descriptors`. Lossless.
2. **`models`** — one row / model or set (`ModelRecord`): `id` (PK, set-level
   content hash), pub_id (FK), model_name, model_type, response,
   covariates, prediction_function, covt_defs, response_definition,
   description, notes, set-level taxa/region/component/descriptors,
   source_file.
3. **`model_specs`** — one row / spec (`ModelSpecRecord`): model_id (FK),
   spec_index, `parameters` (list of {name, value}), and spec scope
   (taxa/region/component/descriptors) **fallback-resolved** from the set.
   PK = composite (model_id, spec_index).

Decisions:
1. **`model_specs` is thin** — consumers join `models` for set-level context.
2. **Set→spec fallback resolution is allowed** (documented inheritance, not the
   banned pub→model "write-over").
3. **`parameters` as a list of {name, value}** (R-friendly), not a map.
4. **Keep the `models` table** (for dedupe/audit and set-level scope), even
   though `model_specs` is the queryable surface.

Flattening: `fixed_effects` → one spec row (spec_index 0); `fixed_effects_set`
→ one row per `specifications` entry. Content hash stays at set granularity.

Supersedes the earlier "widen pub_descriptors onto model rows" idea: with
joins, scopes stay separate with no denormalization.
