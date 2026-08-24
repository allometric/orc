from pathlib import Path

import yaml

from orc.ids import is_valid_id
from orc.records import flatten
from orc.schema import ModelsFile

PUBLICATIONS = Path(__file__).resolve().parent.parent / "publications"


def _load(name: str) -> ModelsFile:
    text = (PUBLICATIONS / name).read_text()
    return ModelsFile.model_validate(yaml.safe_load(text))


def test_barnes_flattens_to_one_spec():
    pub, models, specs = flatten(_load("barnes_1962.yaml"), "barnes_1962.yaml")
    assert pub.pub_id == "barnes_1962"
    assert len(models) == 1
    assert len(specs) == 1
    spec = specs[0]
    assert spec.spec_index == 0
    assert spec.id == models[0].id
    assert spec.set_id == models[0].id
    assert {p.name for p in spec.parameters} == {"a", "b", "c"}


def test_hahn_flattens_to_one_spec_per_row():
    pub, models, specs = flatten(_load("hahn_1991.yaml"), "hahn_1991.yaml")
    assert len(models) == 1
    assert len(specs) == 2
    assert [s.spec_index for s in specs] == [0, 1]
    assert {s.set_id for s in specs} == {models[0].id}


def test_set_specs_have_unique_content_ids():
    # Every model — including each specification of a set — has its own id.
    _, models, specs = flatten(_load("hahn_1991.yaml"), "hahn_1991.yaml")
    set_id = models[0].id
    spec_ids = [s.id for s in specs]
    assert len(spec_ids) == len(set(spec_ids))
    assert all(is_valid_id(s) for s in spec_ids)
    assert set_id not in spec_ids


def test_spec_id_is_content_addressed():
    # Editing one specification's parameters re-ids only that model.
    text = (PUBLICATIONS / "hahn_1991.yaml").read_text()
    data = yaml.safe_load(text)
    before = [s.id for s in flatten(_load("hahn_1991.yaml"), "hahn_1991.yaml")[2]]
    data["model_sets"][0]["specifications"][0]["parameters"]["b_1"] = 999.0
    tmp = Path("__tmp_hahn.yaml")
    try:
        tmp.write_text(yaml.safe_dump(data, sort_keys=False))
        rebuilt = ModelsFile.model_validate(yaml.safe_load(tmp.read_text()))
        after = [s.id for s in flatten(rebuilt, "hahn_1991.yaml")[2]]
    finally:
        tmp.unlink(missing_ok=True)
    assert after[0] != before[0]
    assert after[1] == before[1]


def test_spec_id_stable_under_spec_reordering():
    text = (PUBLICATIONS / "hahn_1991.yaml").read_text()
    data = yaml.safe_load(text)
    data["model_sets"][0]["specifications"].reverse()
    tmp = Path("__tmp_hahn.yaml")
    try:
        tmp.write_text(yaml.safe_dump(data, sort_keys=False))
        rebuilt = ModelsFile.model_validate(yaml.safe_load(tmp.read_text()))
        reordered = [s.id for s in flatten(rebuilt, "hahn_1991.yaml")[2]]
    finally:
        tmp.unlink(missing_ok=True)
    before = {s.id for s in flatten(_load("hahn_1991.yaml"), "hahn_1991.yaml")[2]}
    # ids follow content, not position
    assert set(reordered) == before
    assert len(reordered) == len(set(reordered))


def test_hahn_spec_scope_is_per_spec():
    _, _, specs = flatten(_load("hahn_1991.yaml"), "hahn_1991.yaml")
    # no set-level taxa; each spec carries its own
    assert specs[0].taxa and specs[0].taxa[0].genus == "Pinus"
    assert specs[1].taxa and specs[1].taxa[0].genus == "Acer"


def test_model_record_carries_response_and_covariates():
    _, models, _ = flatten(_load("barnes_1962.yaml"), "barnes_1962.yaml")
    m = models[0]
    assert m.response.name == "hstix50"
    assert m.response.units == "ft"
    assert {c.name for c in m.covariates} == {"atb", "hst"}


def test_single_model_spec_falls_back_to_model_scope():
    pub, models, specs = flatten(_load("barnes_1962.yaml"), "barnes_1962.yaml")
    spec = specs[0]
    assert spec.taxa == models[0].taxa  # inherited from model level
