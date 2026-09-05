from pathlib import Path
import shutil

import duckdb
import yaml

from orc.ingest import ingest
from orc.schema import ModelsFile
from orc.writer import write_parquet

PUBLICATIONS = Path(__file__).resolve().parent.parent / "publications"
MODEL_FAMILIES = Path(__file__).resolve().parent.parent / "model_families"

EMPTY_COUNTS = {
    "publications": 0,
    "models": 0,
    "model_specs": 0,
    "families": 0,
    "family_blobs": 0,
    "family_members": 0,
}


def _write(tmp_path: Path) -> dict[str, int]:
    files = []
    for name in ("barnes_1962.yaml", "hahn_1991.yaml"):
        mf = ModelsFile.model_validate(
            yaml.safe_load((PUBLICATIONS / name).read_text())
        )
        files.append((PUBLICATIONS / name, mf))
    return write_parquet(files, tmp_path)


def _corpus(tmp_path: Path) -> Path:
    """A directory with the repo's publications + model_families."""
    root = tmp_path / "corpus"
    for src in (PUBLICATIONS, MODEL_FAMILIES):
        dest = root / src.name
        dest.mkdir(parents=True)
        for f in src.glob("*.yaml"):
            shutil.copy(f, dest / f.name)
    return root


def _read(con: duckdb.DuckDBPyConnection, table: str, tmp_path: Path):
    return con.execute(f"SELECT * FROM read_parquet('{tmp_path / (table + '.parquet')}')")


def test_writes_six_files(tmp_path):
    counts = _write(tmp_path)
    assert counts == {**EMPTY_COUNTS, "publications": 2, "models": 2, "model_specs": 3}
    for table in EMPTY_COUNTS:
        assert (tmp_path / f"{table}.parquet").exists()


def test_join_specs_to_models_and_publications(tmp_path):
    _write(tmp_path)
    con = duckdb.connect()
    rows = con.execute(
        f"""
        SELECT s.id, s.set_id, m.id, p.pub_id, m.model_name, s.spec_index
        FROM read_parquet('{tmp_path}/model_specs.parquet') s
        JOIN read_parquet('{tmp_path}/models.parquet') m ON m.id = s.set_id
        JOIN read_parquet('{tmp_path}/publications.parquet') p ON p.pub_id = m.pub_id
        ORDER BY s.spec_index
        """
    ).fetchall()
    assert len(rows) == 3
    # every model row carries its own unique id
    assert len({r[0] for r in rows}) == 3
    # specs of a set are distinct from their set's container id
    for spec_id, set_id, model_id, _, model_name, _ in rows:
        assert spec_id == set_id if model_name == "hstix50" else spec_id != set_id
        assert set_id == model_id
    assert {r[4] for r in rows} == {"hstix50", "cuvol"}
    assert sorted(r[5] for r in rows) == [0, 0, 1]


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
    assert counts == EMPTY_COUNTS
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
    rows = con.execute(
        f"DESCRIBE SELECT * FROM read_parquet('{tmp_path}/families.parquet')"
    ).fetchall()
    dtypes = {row[0]: row[1] for row in rows}
    assert dtypes["maintainers"] == "JSON"
    assert dtypes["id"] == "VARCHAR"


def test_ingest_then_write_parquet(tmp_path):
    out = tmp_path / "registry"
    result = ingest(PUBLICATIONS)
    assert result.ok
    counts = write_parquet(result.files, out)
    assert counts["models"] == 2
    assert counts["model_specs"] == 3


def test_family_tables_and_membership(tmp_path):
    root = _corpus(tmp_path)
    out = tmp_path / "registry"
    result = ingest(root)
    assert result.ok, [e.render() for e in result.errors]
    assert len(result.family_files) == 1

    counts = write_parquet(result.files, out, family_files=result.family_files)
    assert counts["families"] == 1
    assert counts["family_blobs"] == 3
    # red/jack pine -> cuvol spec 0; sugar maple -> cuvol spec 1
    assert counts["family_members"] == 3

    con = duckdb.connect()
    rows = con.execute(
        f"""
        SELECT fm.blob_id, m.model_name, p.pub_id, fm.spec_index
        FROM read_parquet('{out}/family_members.parquet') fm
        JOIN read_parquet('{out}/model_specs.parquet') s ON s.id = fm.model_id
        JOIN read_parquet('{out}/models.parquet') m ON m.id = s.set_id
        JOIN read_parquet('{out}/publications.parquet') p ON p.pub_id = m.pub_id
        ORDER BY fm.blob_id
        """
    ).fetchall()
    assert {r[0] for r in rows} == {
        "red_pine_stem_volume",
        "jack_pine_stem_volume",
        "sugar_maple_stem_volume",
    }
    assert {r[1] for r in rows} == {"cuvol"}
    assert all(r[2] == "hahn_1991" for r in rows)
    assert sorted(r[3] for r in rows) == [0, 0, 1]


def test_family_blobs_columns_typed(tmp_path):
    root = _corpus(tmp_path)
    out = tmp_path / "registry"
    result = ingest(root)
    write_parquet(result.files, out, family_files=result.family_files)
    con = duckdb.connect()
    rows = con.execute(
        f"DESCRIBE SELECT * FROM read_parquet('{out}/family_blobs.parquet')"
    ).fetchall()
    dtypes = {row[0]: row[1] for row in rows}
    assert dtypes["covariates"] == "VARCHAR[]"
    assert dtypes["select_taxa"].startswith("STRUCT(")
    assert dtypes["select_descriptors"] == "JSON"


def test_family_select_roundtrip(tmp_path):
    root = _corpus(tmp_path)
    out = tmp_path / "registry"
    result = ingest(root)
    write_parquet(result.files, out, family_files=result.family_files)
    con = duckdb.connect()
    rows = con.execute(
        f"""
        SELECT blob_id, select_taxa.genus, select_taxa.species
        FROM read_parquet('{out}/family_blobs.parquet')
        ORDER BY blob_id
        """
    ).fetchall()
    by_id = {r[0]: r[1:] for r in rows}
    assert by_id["red_pine_stem_volume"] == ("Pinus", "resinosa")
    assert by_id["jack_pine_stem_volume"] == ("Pinus", "banksiana")
    assert by_id["sugar_maple_stem_volume"] == ("Acer", "saccharum")
