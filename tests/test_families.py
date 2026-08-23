from pathlib import Path

import pytest
from pydantic import ValidationError

from orc.families import ModelFamily

FAMILIES = Path(__file__).resolve().parent.parent / "model_families"


def _valid() -> dict:
    return {
        "family": {
            "id": "north_central_stem_volume",
            "title": "Stem volume equations for North Central US tree species",
            "description": "Curated volume equations for North Central US species.",
            "maintainers": [{"name": "Jane Doe", "email": "jane.doe@example.com"}],
        },
        "model_blobs": [
            {
                "id": "red_pine_stem_volume",
                "label": "Red pine (Pinus resinosa)",
                "response": "cuvol",
                "covariates": ["dsob"],
                "select": {
                    "taxa": {"genus": "Pinus", "species": "resinosa"},
                    "region": ["US-MN", "US-WI"],
                },
            }
        ],
    }


def test_valid_example_loads():
    import yaml

    data = yaml.safe_load((FAMILIES / "north_central_stem_volume.yaml").read_text())
    parsed = ModelFamily.model_validate(data)
    assert parsed.family.id == "north_central_stem_volume"
    assert [b.id for b in parsed.model_blobs] == [
        "red_pine_stem_volume",
        "jack_pine_stem_volume",
        "sugar_maple_stem_volume",
    ]
    assert [b.label for b in parsed.model_blobs] == [
        "Red pine (Pinus resinosa)",
        "Jack pine (Pinus banksiana)",
        "Sugar maple (Acer saccharum)",
    ]
    assert all(b.response == "cuvol" for b in parsed.model_blobs)
    assert all(b.covariates == ["dsob"] for b in parsed.model_blobs)


def test_valid_family_parses():
    parsed = ModelFamily.model_validate(_valid())
    assert parsed.family.id == "north_central_stem_volume"
    assert parsed.model_blobs[0].id == "red_pine_stem_volume"
    assert parsed.model_blobs[0].response == "cuvol"
    assert parsed.model_blobs[0].covariates == ["dsob"]
    assert parsed.model_blobs[0].select.taxa.species == "resinosa"
    assert parsed.model_blobs[0].select.region == ["US-MN", "US-WI"]


def test_family_without_structure_ok():
    # families are loose: response/covariates live on blobs, not the family
    data = _valid()
    assert "response" not in data["family"]
    assert "covariates" not in data["family"]
    ModelFamily.model_validate(data)


def test_missing_blob_response_rejected():
    data = _valid()
    del data["model_blobs"][0]["response"]
    with pytest.raises(ValidationError):
        ModelFamily.model_validate(data)


def test_missing_blob_covariates_rejected():
    data = _valid()
    del data["model_blobs"][0]["covariates"]
    with pytest.raises(ValidationError):
        ModelFamily.model_validate(data)


def test_empty_blob_covariates_accepted():
    data = _valid()
    data["model_blobs"][0]["covariates"] = []
    parsed = ModelFamily.model_validate(data)
    assert parsed.model_blobs[0].covariates == []


def test_blobs_may_differ_in_structure():
    data = _valid()
    data["model_blobs"].append(
        {
            "id": "red_pine_biomass",
            "label": "Red pine biomass",
            "response": "mass",
            "covariates": ["dbh"],
            "select": {"taxa": {"genus": "Pinus", "species": "resinosa"}},
        }
    )
    parsed = ModelFamily.model_validate(data)
    assert [b.response for b in parsed.model_blobs] == ["cuvol", "mass"]


def test_missing_model_blobs_rejected():
    data = _valid()
    del data["model_blobs"]
    with pytest.raises(ValidationError):
        ModelFamily.model_validate(data)


def test_empty_model_blobs_rejected():
    data = _valid()
    data["model_blobs"] = []
    with pytest.raises(ValidationError):
        ModelFamily.model_validate(data)


def test_empty_description_rejected():
    data = _valid()
    data["family"]["description"] = ""
    with pytest.raises(ValidationError):
        ModelFamily.model_validate(data)


def test_unknown_family_key_rejected():
    data = _valid()
    data["family"]["bogus"] = "x"
    with pytest.raises(ValidationError):
        ModelFamily.model_validate(data)


def test_unknown_select_key_rejected():
    data = _valid()
    data["model_blobs"][0]["select"]["bogus"] = "x"
    with pytest.raises(ValidationError):
        ModelFamily.model_validate(data)


def test_empty_select_rejected():
    data = _valid()
    data["model_blobs"][0]["select"] = {}
    with pytest.raises(ValidationError):
        ModelFamily.model_validate(data)


def test_invalid_model_id_rejected():
    data = _valid()
    data["model_blobs"][0]["select"] = {"model_id": "zzzzzzzz"}
    with pytest.raises(ValidationError):
        ModelFamily.model_validate(data)


def test_valid_model_id_accepted():
    data = _valid()
    data["model_blobs"][0]["select"] = {"model_id": "a1b2c3d4"}
    parsed = ModelFamily.model_validate(data)
    assert parsed.model_blobs[0].select.model_id == "a1b2c3d4"


def test_taxa_requires_level():
    data = _valid()
    data["model_blobs"][0]["select"] = {"taxa": {}}
    with pytest.raises(ValidationError):
        ModelFamily.model_validate(data)


def test_label_optional():
    data = _valid()
    del data["model_blobs"][0]["label"]
    parsed = ModelFamily.model_validate(data)
    assert parsed.model_blobs[0].label is None


def test_missing_blob_id_rejected():
    data = _valid()
    del data["model_blobs"][0]["id"]
    with pytest.raises(ValidationError):
        ModelFamily.model_validate(data)


def test_invalid_blob_id_rejected():
    data = _valid()
    data["model_blobs"][0]["id"] = "Red Pine Stem Volume"
    with pytest.raises(ValidationError):
        ModelFamily.model_validate(data)


def test_duplicate_blob_ids_rejected():
    data = _valid()
    data["model_blobs"].append(dict(data["model_blobs"][0]))
    with pytest.raises(ValidationError):
        ModelFamily.model_validate(data)


def test_missing_maintainers_rejected():
    data = _valid()
    del data["family"]["maintainers"]
    with pytest.raises(ValidationError):
        ModelFamily.model_validate(data)


def test_empty_maintainers_rejected():
    data = _valid()
    data["family"]["maintainers"] = []
    with pytest.raises(ValidationError):
        ModelFamily.model_validate(data)


def test_maintainer_requires_name():
    data = _valid()
    data["family"]["maintainers"] = [{"email": "jane.doe@example.com"}]
    with pytest.raises(ValidationError):
        ModelFamily.model_validate(data)


def test_maintainer_contact_optional():
    data = _valid()
    data["family"]["maintainers"] = [{"name": "Jane Doe"}]
    parsed = ModelFamily.model_validate(data)
    assert parsed.family.maintainers[0].email is None


def test_unknown_maintainer_key_rejected():
    data = _valid()
    data["family"]["maintainers"] = [{"name": "Jane Doe", "bogus": 1}]
    with pytest.raises(ValidationError):
        ModelFamily.model_validate(data)


def test_maintainer_institution_and_role_accepted():
    data = _valid()
    data["family"]["maintainers"] = [
        {"name": "Jane Doe", "institution": "Univ. of Washington", "role": ["aut", "cre"]}
    ]
    parsed = ModelFamily.model_validate(data)
    m = parsed.family.maintainers[0]
    assert m.institution == "Univ. of Washington"
    assert m.role == ["aut", "cre"]


def test_maintainer_role_accepts_single_string():
    data = _valid()
    data["family"]["maintainers"] = [{"name": "Jane Doe", "role": "cre"}]
    parsed = ModelFamily.model_validate(data)
    assert parsed.family.maintainers[0].role == "cre"


def test_maintainer_unknown_role_rejected():
    data = _valid()
    data["family"]["maintainers"] = [{"name": "Jane Doe", "role": "boss"}]
    with pytest.raises(ValidationError):
        ModelFamily.model_validate(data)


def test_descriptors_accepted():
    data = _valid()
    data["family"]["descriptors"] = {"country": "US", "tags": ["volume"]}
    parsed = ModelFamily.model_validate(data)
    assert parsed.family.descriptors["country"] == "US"
