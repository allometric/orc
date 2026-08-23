from pathlib import Path

import yaml

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
    assert spec.model_id == models[0].id
    assert {p.name for p in spec.parameters} == {"a", "b", "c"}


def test_hahn_flattens_to_one_spec_per_row():
    pub, models, specs = flatten(_load("hahn_1991.yaml"), "hahn_1991.yaml")
    assert len(models) == 1
    assert len(specs) == 2
    assert [s.spec_index for s in specs] == [0, 1]
    assert {s.model_id for s in specs} == {models[0].id}


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
