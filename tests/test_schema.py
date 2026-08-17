from pathlib import Path

import pytest
from pydantic import ValidationError

from orc.schema import ModelsFile

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


@pytest.fixture
def barnes_text() -> str:
    return (EXAMPLES / "barnes_1962.yaml").read_text()


def test_valid_examples_load():
    import yaml

    for name in ("barnes_1962.yaml", "hahn_1991.yaml"):
        ModelsFile.model_validate(yaml.safe_load((EXAMPLES / name).read_text()))


def test_missing_required_field(barnes_text):
    import yaml

    data = yaml.safe_load(barnes_text)
    del data["models"][0]["equation"]
    with pytest.raises(ValidationError):
        ModelsFile.model_validate(data)


def test_unknown_field_rejected(barnes_text):
    import yaml

    data = yaml.safe_load(barnes_text)
    data["models"][0]["paramaters"] = {"a": 1.0}  # typo
    with pytest.raises(ValidationError):
        ModelsFile.model_validate(data)


def test_wrong_type_rejected(barnes_text):
    import yaml

    data = yaml.safe_load(barnes_text)
    data["publication"]["year"] = "nineteen-sixty-two"
    with pytest.raises(ValidationError):
        ModelsFile.model_validate(data)


def test_unknown_model_type_rejected(barnes_text):
    import yaml

    data = yaml.safe_load(barnes_text)
    data["models"][0]["type"] = "bayesian_hierarchical"
    with pytest.raises(ValidationError):
        ModelsFile.model_validate(data)


def test_invalid_id_format_rejected(barnes_text):
    import yaml

    data = yaml.safe_load(barnes_text)
    data["models"][0]["id"] = "not-an-id!"
    with pytest.raises(ValidationError):
        ModelsFile.model_validate(data)


def test_empty_models_rejected(barnes_text):
    import yaml

    data = yaml.safe_load(barnes_text)
    data["models"] = []
    with pytest.raises(ValidationError):
        ModelsFile.model_validate(data)
