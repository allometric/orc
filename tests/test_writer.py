from pathlib import Path

import duckdb
import yaml

from orc.ingest import ingest
from orc.schema import ModelsFile
from orc.writer import write_parquet

PUBLICATIONS = Path(__file__).resolve().parent.parent / "publications"


def _write(tmp_path: Path) -> dict[str, int]:
    files = []
    for name in ("barnes_1962.yaml", "hahn_1991.yaml"):
        mf = ModelsFile.model_validate(
            yaml.safe_load((PUBLICATIONS / name).read_text())
        )
        files.append((PUBLICATIONS / name, mf))
    return write_parquet(files, tmp_path)


def _read(con: duckdb.DuckDBPyConnection, table: str, tmp_path: Path):
    return con.execute(f"SELECT * FROM read_parquet('{tmp_path / (table + '.parquet')}')")


def test_writes_three_files(tmp_path):
    counts = _write(tmp_path)
    assert counts == {"publications": 2, "models": 2, "model_specs": 3}
    for table in ("publications", "models", "model_specs"):
        assert (tmp_path / f"{table}.parquet").exists()


def test_join_specs_to_models_and_publications(tmp_path):
    _write(tmp_path)
    con = duckdb.connect()
    rows = con.execute(
        f"""
        SELECT s.model_id, m.id, p.pub_id, m.model_name, s.spec_index
        FROM read_parquet('{tmp_path}/model_specs.parquet') s
        JOIN read_parquet('{tmp_path}/models.parquet') m ON m.id = s.model_id
        JOIN read_parquet('{tmp_path}/publications.parquet') p ON p.pub_id = m.pub_id
        ORDER BY s.spec_index
        """
    ).fetchall()
    assert len(rows) == 3
    assert {r[3] for r in rows} == {"hstix50", "cuvol"}
    assert sorted(r[4] for r in rows) == [0, 0, 1]


def test_columns_are_typed_not_json(tmp_path):
    _write(tmp_path)
    con = duckdb.connect()
    rows = con.execute(
        f"DESCRIBE SELECT * FROM read_parquet('{tmp_path}/model_specs.parquet')"
    ).fetchall()
    dtypes = {row[0]: row[1] for row in rows}
    assert dtypes["parameters"] == 'STRUCT("name" VARCHAR, "value" DOUBLE)[]'
    assert dtypes["region"] == "VARCHAR[]"
    assert dtypes["taxa"] == (
        'STRUCT("family" VARCHAR, genus VARCHAR, species VARCHAR)[]'
    )


def test_parameters_values_are_floats(tmp_path):
    _write(tmp_path)
    con = duckdb.connect()
    vals = con.execute(
        f"SELECT unnest.value FROM read_parquet('{tmp_path}/model_specs.parquet') "
        "CROSS JOIN UNNEST(parameters)"
    ).fetchall()
    assert all(isinstance(v, float) for (v,) in vals)


def test_empty_input_writes_zero_row_typed_parquet(tmp_path):
    counts = write_parquet([], tmp_path)
    assert counts == {"publications": 0, "models": 0, "model_specs": 0}
    con = duckdb.connect()
    n = con.execute(
        f"SELECT count(*) FROM read_parquet('{tmp_path}/model_specs.parquet')"
    ).fetchone()[0]
    assert n == 0
    rows = con.execute(
        f"DESCRIBE SELECT * FROM read_parquet('{tmp_path}/model_specs.parquet')"
    ).fetchall()
    dtypes = {row[0]: row[1] for row in rows}
    assert dtypes["parameters"] == 'STRUCT("name" VARCHAR, "value" DOUBLE)[]'


def test_ingest_then_write_parquet(tmp_path):
    out = tmp_path / "registry"
    result = ingest(PUBLICATIONS)
    assert result.ok
    counts = write_parquet(result.files, out)
    assert counts["models"] == 2
    assert counts["model_specs"] == 3
