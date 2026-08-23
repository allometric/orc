"""Write the compiled Layer-A records to parquet using DuckDB's parquet writer.

Keeps parquet as the committed, engine-agnostic artifact while using duckdb
only as the *writer*, so ``orc`` stays light (no pyarrow dependency). Tables are
written with an explicit per-column type map, so null-only columns come out
properly typed (not JSON) and empty tables still yield a zero-row, correctly
typed parquet file.

Consumers (R ``arrow``, DuckDB, polars, pandas, ...) read the six files
directly and join on ``pub_id`` / ``id`` / ``model_id``; family membership
joins on ``family_id`` / ``blob_id`` + ``model_id`` / ``spec_index``.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Iterable

import duckdb

from orc.families import ModelFamily
from orc.records import (
    FamilyMemberRecord,
    build_family_blob_records,
    build_family_record,
    flatten,
)
from orc.resolve import build_registry_from_files, resolve
from orc.schema import ModelsFile

_TAXA = "STRUCT(family VARCHAR, genus VARCHAR, species VARCHAR)[]"
_TAXA_SINGLE = "STRUCT(family VARCHAR, genus VARCHAR, species VARCHAR)"
_JSON = "JSON"

PUBLICATIONS_COLUMNS: dict[str, str] = {
    "pub_id": "VARCHAR",
    "bibtype": "VARCHAR",
    "title": "VARCHAR",
    "author": "VARCHAR",
    "year": "BIGINT",
    "number": "VARCHAR",
    "institution": "VARCHAR",
    "journal": "VARCHAR",
    "volume": "VARCHAR",
    "pages": "VARCHAR",
    "doi": "VARCHAR",
    "url": "VARCHAR",
    "publisher": "VARCHAR",
    "address": "VARCHAR",
    "month": "VARCHAR",
    "note": "VARCHAR",
    "school": "VARCHAR",
    "organization": "VARCHAR",
    "series": "VARCHAR",
    "booktitle": "VARCHAR",
    "editor": "VARCHAR",
    "howpublished": "VARCHAR",
    "edition": "VARCHAR",
    "descriptors": _JSON,
}

MODELS_COLUMNS: dict[str, str] = {
    "id": "VARCHAR",
    "pub_id": "VARCHAR",
    "model_name": "VARCHAR",
    "model_type": "VARCHAR",
    "response": "STRUCT(name VARCHAR, units VARCHAR)",
    "covariates": "STRUCT(name VARCHAR, units VARCHAR)[]",
    "prediction_function": "VARCHAR",
    "covt_defs": _JSON,
    "response_definition": "VARCHAR",
    "description": "VARCHAR",
    "notes": "VARCHAR",
    "taxa": _TAXA,
    "region": "VARCHAR[]",
    "component": "VARCHAR",
    "descriptors": _JSON,
    "source_file": "VARCHAR",
}

MODEL_SPECS_COLUMNS: dict[str, str] = {
    "model_id": "VARCHAR",
    "spec_index": "BIGINT",
    "parameters": "STRUCT(name VARCHAR, value DOUBLE)[]",
    "taxa": _TAXA,
    "region": "VARCHAR[]",
    "component": "VARCHAR",
    "descriptors": _JSON,
}

FAMILIES_COLUMNS: dict[str, str] = {
    "id": "VARCHAR",
    "title": "VARCHAR",
    "description": "VARCHAR",
    "maintainers": _JSON,
    "pub_id": "VARCHAR",
    "descriptors": _JSON,
}

FAMILY_BLOBS_COLUMNS: dict[str, str] = {
    "family_id": "VARCHAR",
    "blob_id": "VARCHAR",
    "label": "VARCHAR",
    "response": "VARCHAR",
    "covariates": "VARCHAR[]",
    "select_pub_id": "VARCHAR",
    "select_model_id": "VARCHAR",
    "select_model_set_name": "VARCHAR",
    "select_model_name": "VARCHAR",
    "select_taxa": _TAXA_SINGLE,
    "select_region": "VARCHAR[]",
    "select_component": "VARCHAR",
    "select_descriptors": _JSON,
}

FAMILY_MEMBERS_COLUMNS: dict[str, str] = {
    "family_id": "VARCHAR",
    "blob_id": "VARCHAR",
    "model_id": "VARCHAR",
    "spec_index": "BIGINT",
}

_TABLES: list[tuple[str, dict[str, str]]] = [
    ("publications", PUBLICATIONS_COLUMNS),
    ("models", MODELS_COLUMNS),
    ("model_specs", MODEL_SPECS_COLUMNS),
    ("families", FAMILIES_COLUMNS),
    ("family_blobs", FAMILY_BLOBS_COLUMNS),
    ("family_members", FAMILY_MEMBERS_COLUMNS),
]


def _write_table(
    con: duckdb.DuckDBPyConnection,
    table: str,
    columns: dict[str, str],
    rows: list,
    out_dir: Path,
) -> int:
    """Dump ``rows`` (pydantic records) to ``out_dir/<table>.parquet``."""
    fd, tmp = tempfile.mkstemp(suffix=".jsonl", prefix="orc_")
    os.close(fd)
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            for record in rows:
                fh.write(json.dumps(record.model_dump(mode="json")) + "\n")
        colsql = json.dumps(columns)
        out = str((out_dir / f"{table}.parquet").resolve())
        con.execute(
            f"COPY (SELECT * FROM read_json_auto('{tmp}', columns={colsql})) "
            f"TO '{out}' (FORMAT PARQUET)"
        )
    finally:
        os.unlink(tmp)
    return len(rows)


def write_parquet(
    files: Iterable[tuple[Path, ModelsFile]],
    out_dir: str | Path,
    family_files: Iterable[tuple[Path, "ModelFamily"]] | None = None,
) -> dict[str, int]:
    """Flatten every validated ``ModelsFile`` and write six parquet tables.

    ``family_files`` are validated ``ModelFamily`` files; their blobs are
    resolved against the compiled registry and the pinned membership is
    written to ``family_members.parquet``.

    Returns a dict of table name -> row count written.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    publications: list = []
    models: list = []
    model_specs: list = []
    seen_pubs: set[str] = set()
    for path, mf in files:
        pub, mods, specs = flatten(mf, str(path))
        if pub.pub_id not in seen_pubs:  # one file per publication, but be safe
            seen_pubs.add(pub.pub_id)
            publications.append(pub)
        models.extend(mods)
        model_specs.extend(specs)

    families: list = []
    family_blobs: list = []
    family_members: list = []
    family_files = list(family_files or [])
    if family_files:
        registry = build_registry_from_files(list(files))
        for _, family in family_files:
            families.append(build_family_record(family))
            family_blobs.extend(build_family_blob_records(family))
            resolved = resolve(family, registry)
            for blob_result in resolved.blobs:
                for row in blob_result.matched:
                    family_members.append(
                        FamilyMemberRecord(
                            family_id=family.family.id,
                            blob_id=blob_result.blob.id,
                            model_id=row.model_id,
                            spec_index=row.spec_index,
                        )
                    )

    rows = {
        "publications": publications,
        "models": models,
        "model_specs": model_specs,
        "families": families,
        "family_blobs": family_blobs,
        "family_members": family_members,
    }
    with duckdb.connect() as con:
        return {
            table: _write_table(con, table, columns, rows[table], out_dir)
            for table, columns in _TABLES
        }
