"""Declared schema for allometric/models v4 YAML files.

This is a *draft* — the v4 format is still being defined. The structure mirrors
the current publication R files and the v4 sketch:

```yaml
publication: { key, bibtype, title, author, year, ... }
models:
  - name: hstix50
    type: fixed_effects
    response: { hstix50: "ft" }  # {name: units}
    covariates: { atb: "year" }  # {name: units-or-kind}
    parameters: { a: 22.6 }
    prediction_function: "4.5 + a * exp((b - c * log(atb)) * (hst - 4.5))"
model_sets:
  - name: cuvol
    type: fixed_effects_set
    response: { cuvol: "ft3" }
    covariates: { dsob: "in" }
    prediction_function: "b_1 + b_2 * dsob^2"
    specifications:
      - parameters: { b_1: 122.77 }
```

Design choices encoded here:

- ``extra="forbid"`` everywhere: this schema exists to *catch* typos and
  surprises, not to absorb them.
- Top-level ``models`` and ``model_sets`` separate the two structural kinds:
  individual models vs. parameterized families with a ``specifications``
  table. ``type`` is required on every entry and is the extension point for
  future kinds (only ``fixed_effects`` / ``fixed_effects_set`` are valid today).
- ``response``/``covariates`` accept the compact ``{name: value}`` map form from
  the sketch and normalize to objects.
- ``id`` is optional in source; when present it must already be a valid 8-char
  orc id (and ``ingest`` cross-checks it against the derived content hash).
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from orc.ids import is_valid_id

# Common BibTeX entry types; add more only when a real publication needs it.
BIBTYPES = Literal[
    "article",
    "book",
    "booklet",
    "inbook",
    "incollection",
    "inproceedings",
    "manual",
    "mastersthesis",
    "misc",
    "phdthesis",
    "proceedings",
    "techreport",
    "unpublished",
]

ID_PATTERN = re.compile(r"^[0-9a-f]{8}$")

Scalar = str | int | float | bool


def _expand_map(values: Any, value_key: str = "units") -> Any:
    """Turn ``{name: value}`` into an object dict; pass through real objects."""
    if isinstance(values, dict) and "name" not in values and len(values) == 1:
        (name, value), = values.items()
        return {"name": name, value_key: value}
    return values


class Taxon(BaseModel):
    model_config = ConfigDict(extra="forbid")

    family: str | None = None
    genus: str | None = None
    species: str | None = None

    @model_validator(mode="after")
    def _at_least_one_level(self) -> Taxon:
        if self.family is None and self.genus is None and self.species is None:
            raise ValueError("taxon must name at least one of family/genus/species")
        return self


class Response(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    units: str

    @model_validator(mode="before")
    @classmethod
    def _from_map(cls, values: Any) -> Any:
        return _expand_map(values)


class Covariate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    units: str | None = None  # may be a kind/definition (e.g. "year") for now

    @model_validator(mode="before")
    @classmethod
    def _from_map(cls, values: Any) -> Any:
        return _expand_map(values)


class ModelBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    type: str
    prediction_function: str
    response: Response
    covariates: list[Covariate] = Field(default_factory=list)
    taxa: list[Taxon] | None = None
    region: list[str] | None = None
    component: str | None = None
    covt_defs: dict[str, str] | None = None
    response_definition: str | None = None
    descriptors: dict[str, Scalar | list] | None = None
    description: str | None = None
    notes: str | None = None
    id: str | None = Field(default=None, pattern=ID_PATTERN.pattern)

    @model_validator(mode="before")
    @classmethod
    def _normalize(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            return values
        values = dict(values)
        if "response" in values:
            values["response"] = _expand_map(values["response"])
        if "covariates" in values:
            covs = values["covariates"]
            if isinstance(covs, dict):
                values["covariates"] = [
                    {"name": k, "units": v} for k, v in covs.items()
                ]
        return values

    @model_validator(mode="after")
    def _validate_id(self) -> ModelBase:
        if self.id is not None and not is_valid_id(self.id):
            raise ValueError(f"model id must be an 8-char hex string, got {self.id!r}")
        return self


class FixedEffectsModel(ModelBase):
    type: Literal["fixed_effects"]
    parameters: dict[str, float]


class Specification(BaseModel):
    """One row of a parameterized set: parameter values plus optional scope."""

    model_config = ConfigDict(extra="forbid")

    parameters: dict[str, float]
    taxa: list[Taxon] | None = None
    region: list[str] | None = None
    component: str | None = None
    descriptors: dict[str, Scalar | list] | None = None


class FixedEffectsSetModel(ModelBase):
    type: Literal["fixed_effects_set"]
    specifications: list[Specification]

    @model_validator(mode="after")
    def _consistent_parameter_keys(self) -> FixedEffectsSetModel:
        if not self.specifications:
            raise ValueError("a fixed_effects_set needs at least one specification")
        key_sets = [set(spec.parameters) for spec in self.specifications]
        if any(keys != key_sets[0] for keys in key_sets[1:]):
            raise ValueError(
                "all specifications in a set must have identical parameter keys, "
                f"got {sorted({k for ks in key_sets for k in ks})}"
            )
        return self


Model = FixedEffectsModel | FixedEffectsSetModel


class Publication(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    bibtype: BIBTYPES
    title: str
    author: str
    year: int
    number: str | int | None = None
    institution: str | None = None
    journal: str | None = None
    volume: str | int | None = None
    pages: str | None = None
    doi: str | None = None
    url: str | None = None
    publisher: str | None = None
    address: str | None = None
    month: str | None = None
    note: str | None = None
    school: str | None = None
    organization: str | None = None
    series: str | None = None
    booktitle: str | None = None
    editor: str | None = None
    howpublished: str | None = None
    edition: str | None = None
    descriptors: dict[str, Scalar | list] | None = None

    @field_validator("year")
    @classmethod
    def _sane_year(cls, v: int) -> int:
        if v < 1000 or v > 2100:
            raise ValueError(f"implausible year {v}")
        return v


class ModelsFile(BaseModel):
    """Top-level structure of a single publication YAML file.

    Individual models live under ``models``; parameterized families under
    ``model_sets``. At least one of the two must be present.
    """

    model_config = ConfigDict(extra="forbid")

    publication: Publication
    models: list[FixedEffectsModel] = Field(default_factory=list)
    model_sets: list[FixedEffectsSetModel] = Field(default_factory=list)

    @model_validator(mode="after")
    def _at_least_one_model_kind(self) -> ModelsFile:
        if not self.models and not self.model_sets:
            raise ValueError("at least one of models or model_sets is required")
        return self

    @model_validator(mode="after")
    def _unique_model_names(self) -> ModelsFile:
        names = [m.name for m in self.models] + [s.name for s in self.model_sets]
        dupes = {n for n in names if names.count(n) > 1}
        if dupes:
            raise ValueError(f"duplicate model names in file: {sorted(dupes)}")
        return self


class RegistryRecord(BaseModel):
    """Flat, one-model-per-row view for the compiled registry."""

    model_config = ConfigDict(extra="forbid")

    id: str
    pub_id: str
    pub_year: int
    model_name: str
    model_type: str
    response: Response
    covariates: list[Covariate]
    parameters: dict[str, float] | None = None
    prediction_function: str
    parameter_names: list[str] | None = None
    taxa: list[Taxon] | None = None
    region: list[str] | None = None
    component: str | None = None
    covt_defs: dict[str, str] | None = None
    response_definition: str | None = None
    description: str | None = None
    descriptors: dict[str, Scalar | list] | None = None
    source_file: str