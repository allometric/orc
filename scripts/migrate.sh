#!/usr/bin/env bash
# One-off migration: R publication files -> neutral JSON -> v4 YAML -> orc validation.
#
# THROWAWAY tooling: run once to produce the v4 YAML corpus, then the R source
# and these scripts can be deleted.
#
# Usage:
#   ./scripts/migrate.sh <models_repo_root> <out_dir>
# e.g.
#   ./scripts/migrate.sh /path/to/allometric/models ./models_v4
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODELS_ROOT="${1:?usage: migrate.sh <models_repo_root> <out_dir>}"
OUT_DIR="${2:?usage: migrate.sh <models_repo_root> <out_dir>}"

HARVEST_DIR="$OUT_DIR/_harvest"
mkdir -p "$HARVEST_DIR"

echo "== step 1/3: harvest R publications -> JSON =="
Rscript "$REPO_ROOT/scripts/harvest.R" \
  "$MODELS_ROOT/publications" \
  "$MODELS_ROOT/parameters" \
  "$HARVEST_DIR"

echo "== step 2/3: JSON -> v4 YAML =="
"$REPO_ROOT/.venv/bin/python" "$REPO_ROOT/scripts/convert.py" "$HARVEST_DIR" "$OUT_DIR"

echo "== step 3/3: orc ingest validates the corpus =="
"$REPO_ROOT/.venv/bin/orc" ingest "$OUT_DIR" --registry "$OUT_DIR/registry.jsonl" \
  || { echo "migration produced invalid YAML"; exit 1; }

echo "done. YAML corpus: $OUT_DIR"