from pathlib import Path

import yaml

from orc.ingest import ingest
from orc.ids import is_valid_id
from orc.schema import ModelsFile

PUBLICATIONS = Path(__file__).resolve().parent.parent / "publications"


def test_ingest_examples_ok():
    result = ingest(PUBLICATIONS)
    assert result.ok, [e.render() for e in result.errors]
    assert {r.pub_id for r in result.registry} == {"barnes_1962", "hahn_1991"}


def test_every_model_has_valid_unique_id():
    result = ingest(PUBLICATIONS)
    ids = [r.id for r in result.registry]
    assert all(is_valid_id(i) for i in ids)
    assert len(ids) == len(set(ids))


def test_set_specs_are_distinct_registry_models():
    # Each specification of a set is its own model with its own parameters
    # and id — never the shared set id.
    result = ingest(PUBLICATIONS)
    hahn = [r for r in result.registry if r.pub_id == "hahn_1991"]
    assert len(hahn) == 2
    assert len({r.id for r in hahn}) == 2
    assert all(r.parameters is not None for r in hahn)
    assert {r.parameters["b_1"] for r in hahn} == {122.77, 0.25}


def test_id_is_content_addressed():
    result = ingest(PUBLICATIONS)
    barnes = next(r for r in result.registry if r.model_name == "hstix50")
    text = (PUBLICATIONS / "barnes_1962.yaml").read_text()
    data = yaml.safe_load(text)
    # reformatting (reorder keys) must not change the id
    data["models"][0] = {k: data["models"][0][k] for k in reversed(list(data["models"][0]))}
    rebuilt = ModelsFile.model_validate(data)
    from orc.ingest import model_id

    assert model_id(rebuilt.models[0]) == barnes.id


def test_source_id_mismatch_reported():
    text = (PUBLICATIONS / "barnes_1962.yaml").read_text()
    data = yaml.safe_load(text)
    data["models"][0]["id"] = "deadbeef"
    tmp = Path("__tmp_barnes.yaml")
    try:
        tmp.write_text(yaml.safe_dump(data, sort_keys=False))
        result = ingest(tmp)
        assert not result.ok
        assert any("does not match content hash" in e.message for e in result.errors)
    finally:
        tmp.unlink(missing_ok=True)


def test_set_parameter_consistency():
    text = (PUBLICATIONS / "hahn_1991.yaml").read_text()
    data = yaml.safe_load(text)
    data["model_sets"][0]["specifications"][0]["parameters"]["b_99"] = 1.0
    tmp = Path("__tmp_hahn.yaml")
    try:
        tmp.write_text(yaml.safe_dump(data, sort_keys=False))
        result = ingest(tmp)
        assert not result.ok
        assert any("identical parameter keys" in e.message for e in result.errors)
    finally:
        tmp.unlink(missing_ok=True)


def test_single_file_ingest():
    result = ingest(PUBLICATIONS / "barnes_1962.yaml")
    assert result.ok
    assert len(result.registry) == 1


def test_hidden_directories_skipped(tmp_path):
    # a workflow yaml under .github must not be parsed as a models file
    hidden = tmp_path / ".github" / "workflows"
    hidden.mkdir(parents=True)
    (hidden / "build.yaml").write_text("name: build\non: push\njobs: {}\n")
    # corpus file still ingested
    data = yaml.safe_load((PUBLICATIONS / "barnes_1962.yaml").read_text())
    (tmp_path / "barnes_1962.yaml").write_text(yaml.safe_dump(data, sort_keys=False))

    result = ingest(tmp_path)
    assert result.ok, [e.render() for e in result.errors]
    assert {r.pub_id for r in result.registry} == {"barnes_1962"}


def _family_yaml(family_id: str) -> dict:
    return {
        "family": {
            "id": family_id,
            "title": "Test family",
            "description": "Test.",
            "maintainers": [{"name": "Jane Doe"}],
        },
        "model_blobs": [
            {
                "id": "b1",
                "response": "cuvol",
                "covariates": ["dsob"],
                "select": {"model_set_name": "cuvol"},
            }
        ],
    }


def test_ingest_family_file_collected(tmp_path):
    path = tmp_path / "test_fam.yaml"
    path.write_text(yaml.safe_dump(_family_yaml("test_fam"), sort_keys=False))
    result = ingest(tmp_path)
    assert result.ok, [e.render() for e in result.errors]
    assert len(result.family_files) == 1
    assert result.family_files[0][1].family.id == "test_fam"


def test_family_id_must_match_filename_stem(tmp_path):
    path = tmp_path / "other_name.yaml"
    path.write_text(yaml.safe_dump(_family_yaml("test_fam"), sort_keys=False))
    result = ingest(tmp_path)
    assert not result.ok
    assert any("filename stem" in e.message for e in result.errors)


def test_duplicate_family_id_reported(tmp_path):
    (tmp_path / "test_fam.yaml").write_text(
        yaml.safe_dump(_family_yaml("test_fam"), sort_keys=False)
    )
    (tmp_path / "test_fam_dup.yaml").write_text(
        yaml.safe_dump(_family_yaml("test_fam"), sort_keys=False)
    )
    result = ingest(tmp_path)
    assert not result.ok
    assert any("duplicate family id" in e.message for e in result.errors)
