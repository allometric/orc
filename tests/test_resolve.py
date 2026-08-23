from pathlib import Path

import yaml

from orc.families import ModelFamily
from orc.resolve import build_registry, resolve

ROOT = Path(__file__).resolve().parent.parent
PUBLICATIONS = ROOT / "publications"


def _family(model_blobs: list[dict]) -> ModelFamily:
    return ModelFamily.model_validate(
        {
            "family": {
                "id": "test_family",
                "title": "Test family",
                "description": "Test.",
                "maintainers": [{"name": "Jane Doe"}],
            },
            "model_blobs": model_blobs,
        }
    )


def _blob(blob_id: str, response: str, covariates: list[str], select: dict) -> dict:
    return {
        "id": blob_id,
        "response": response,
        "covariates": covariates,
        "select": select,
    }


def test_registry_built_from_publications():
    rows = build_registry(PUBLICATIONS)
    # barnes hstix50 (1 spec) + hahn cuvol (2 specs)
    assert len(rows) == 3
    names = {(r.model_name, r.spec_index) for r in rows}
    assert names == {("hstix50", 0), ("cuvol", 0), ("cuvol", 1)}


def test_resolve_by_model_name():
    family = _family(
        [_blob("si", "hstix50", ["atb", "hst"], {"model_name": "hstix50"})]
    )
    result = resolve(family, build_registry(PUBLICATIONS))
    assert result.ok, result.errors
    assert [r.model_name for r in result.blobs[0].matched] == ["hstix50"]


def test_resolve_taxa_matches_partial_levels():
    # Pinus genus: matches the cuvol spec covering Pinus resinosa/strobus/banksiana.
    family = _family(
        [_blob("vol", "cuvol", ["dsob"], {"taxa": {"genus": "Pinus"}})]
    )
    result = resolve(family, build_registry(PUBLICATIONS))
    assert result.ok, result.errors
    assert len(result.blobs[0].matched) == 1
    assert "Pinus" in result.blobs[0].matched[0].identity()


def test_resolve_model_set_name():
    family = _family(
        [_blob("vol", "cuvol", ["dsob"], {"model_set_name": "cuvol"})]
    )
    result = resolve(family, build_registry(PUBLICATIONS))
    assert result.ok, result.errors
    # both cuvol specifications (Pinus resinosa, Acer saccharum)
    assert len(result.blobs[0].matched) == 2


def test_resolve_pub_id_scope():
    family = _family(
        [
            _blob(
                "vol",
                "cuvol",
                ["dsob"],
                {"pub_id": "hahn_1991", "model_set_name": "cuvol"},
            )
        ]
    )
    result = resolve(family, build_registry(PUBLICATIONS))
    assert result.ok, result.errors
    assert all(r.pub_id == "hahn_1991" for r in result.blobs[0].matched)


def test_empty_blob_is_error():
    family = _family(
        [_blob("ghost", "cuvol", ["dsob"], {"model_name": "nope"})]
    )
    result = resolve(family, build_registry(PUBLICATIONS))
    assert not result.ok
    assert any("no models" in e for e in result.errors)


def test_invariant_response_mismatch():
    family = _family(
        [_blob("vol", "mass", ["dsob"], {"model_set_name": "cuvol"})]
    )
    result = resolve(family, build_registry(PUBLICATIONS))
    assert not result.ok
    assert any("declares 'mass'" in e for e in result.errors)


def test_invariant_covariate_mismatch():
    family = _family(
        [_blob("vol", "cuvol", ["dbh"], {"model_set_name": "cuvol"})]
    )
    result = resolve(family, build_registry(PUBLICATIONS))
    assert not result.ok
    assert any("covariates" in e for e in result.errors)


def test_invariants_ok_across_mixed_taxa():
    # Both cuvol specs share response cuvol [ft3] and covariates [dsob].
    family = _family(
        [_blob("vol", "cuvol", ["dsob"], {"model_set_name": "cuvol"})]
    )
    result = resolve(family, build_registry(PUBLICATIONS))
    assert result.ok, result.errors
    assert len(result.blobs[0].matched) == 2


def test_doe_2024_example_resolves(tmp_path):
    # Reproduce the docs example end-to-end via a temp publication + family.
    pub = {
        "publication": {
            "key": "doe_2024",
            "bibtype": "article",
            "title": "Growth and yield of a mixed conifer stand",
            "author": "Doe, Jane",
            "year": 2024,
        },
        "models": [
            {
                "name": "hstix50",
                "type": "fixed_effects",
                "response": {"hstix50": "ft"},
                "covariates": {"atb": "year", "hst": "ft"},
                "taxa": [{"family": "Pinaceae", "genus": "Tsuga", "species": "heterophylla"}],
                "parameters": {"a": 22.6, "b": 0.014482, "c": 0.001162},
                "prediction_function": "4.5 + a * exp((b - c * log(atb)) * (hst - 4.5))",
            }
        ],
        "model_sets": [
            {
                "name": "cuvol",
                "type": "fixed_effects_set",
                "response": {"cuvol": "ft3"},
                "covariates": {"dsob": "in"},
                "prediction_function": "b_1 + b_2 * dsob^2",
                "specifications": [
                    {"parameters": {"b_1": 122.77, "b_2": 0.4148},
                     "taxa": [{"genus": "Pinus", "species": "resinosa"}]},
                    {"parameters": {"b_1": 0.25, "b_2": 1.3},
                     "taxa": [{"genus": "Acer", "species": "saccharum"}]},
                ],
            }
        ],
    }
    pub_file = tmp_path / "doe_2024.yaml"
    pub_file.write_text(yaml.safe_dump(pub, sort_keys=False))

    family = _family(
        [
            _blob("hemlock_site_index", "hstix50", ["atb", "hst"],
                  {"pub_id": "doe_2024", "model_name": "hstix50"}),
            _blob("red_pine_stem_volume", "cuvol", ["dsob"],
                  {"pub_id": "doe_2024", "taxa": {"genus": "Pinus", "species": "resinosa"}}),
            _blob("sugar_maple_stem_volume", "cuvol", ["dsob"],
                  {"pub_id": "doe_2024", "taxa": {"genus": "Acer", "species": "saccharum"}}),
        ]
    )
    result = resolve(family, build_registry(tmp_path))
    assert result.ok, result.errors
    assert [len(b.matched) for b in result.blobs] == [1, 1, 1]
    identities = [b.matched[0].identity() for b in result.blobs]
    assert identities == [
        "hstix50",
        "cuvol spec Pinus resinosa",
        "cuvol spec Acer saccharum",
    ]
