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
    del data["models"][0]["prediction_function"]
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


def test_set_missing_prediction_function_rejected(barnes_text):
    import yaml

    data = yaml.safe_load(barnes_text)
    data["models"][0] = {
        "name": "set",
        "type": "fixed_effects_set",
        "response": { "x": "m" },
        "specifications": [{ "parameters": { "a": 1.0 } }],
    }
    with pytest.raises(ValidationError):
        ModelsFile.model_validate(data)


def test_set_parameter_keys_must_match(barnes_text):
    import yaml

    data = yaml.safe_load(barnes_text)
    data["models"][0] = {
        "name": "set",
        "type": "fixed_effects_set",
        "response": { "x": "m" },
        "prediction_function": "a * x^b",
        "specifications": [
            { "parameters": { "a": 1.0, "b": 2.0 } },
            { "parameters": { "a": 3.0, "c": 4.0 } },
        ],
    }
    with pytest.raises(ValidationError, match="identical parameter keys"):
        ModelsFile.model_validate(data)


def test_set_parameter_names_derived(barnes_text):
    import yaml

    data = yaml.safe_load(barnes_text)
    data["models"][0] = {
        "name": "set",
        "type": "fixed_effects_set",
        "response": { "x": "m" },
        "prediction_function": "a * x^b",
        "specifications": [
            { "parameters": { "b": 2.0, "a": 1.0 } },
            { "parameters": { "b": 3.0, "a": 4.0 } },
        ],
    }
    parsed = ModelsFile.model_validate(data)
    assert [p for p in parsed.models[0].specifications[0].parameters] == ["b", "a"]


def test_set_parameter_key_order_irrelevant(barnes_text):
    import yaml

    data = yaml.safe_load(barnes_text)
    data["models"][0] = {
        "name": "set",
        "type": "fixed_effects_set",
        "response": { "x": "m" },
        "prediction_function": "a * x^b",
        "specifications": [
            { "parameters": { "a": 1.0, "b": 2.0 } },
            { "parameters": { "b": 3.0, "a": 4.0 } },
        ],
    }
    ModelsFile.model_validate(data)


def test_description_accepted(barnes_text):
    import yaml

    data = yaml.safe_load(barnes_text)
    data["models"][0]["description"] = "Height of dominant trees, log-log."
    parsed = ModelsFile.model_validate(data)
    assert parsed.models[0].description == "Height of dominant trees, log-log."


def test_description_rejected_when_non_string(barnes_text):
    import yaml

    data = yaml.safe_load(barnes_text)
    data["models"][0]["description"] = 42
    with pytest.raises(ValidationError):
        ModelsFile.model_validate(data)
