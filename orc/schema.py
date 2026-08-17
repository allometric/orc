"""Declared schema for allometric/models v4 YAML files.

This is a *draft* — the v4 format is still being defined. The structure mirrors
the current publication R files and the v4 sketch:

```yaml
publication: { key, bibtype, title, author, year, ... }
models:
  - name: hstix50
    type: fixed_effects          # or fixed_effects_set
    response: { hstix50: "ft" }  # {name: units}
    covariates: { atb: "year" }  # {name: units-or-kind}
    parameters: { a: 22.6 }
    equation: "..."
```

Design choices encoded here:

- ``extra="forbid"`` everywhere: this schema exists to *catch* typos and
  surprises, not to absorb them.
- ``type`` discriminates the two structural kinds of model (inline parameters
  vs. a parameterized set with a specifications table).
- ``response``/``covariates`` accept the compact ``{name: value}`` map form from
  the sketch and normalize to objects.
- ``id`` is optional in source; when present it must already be a valid 8-char
  orc id (and ``ingest`` cross-checks it against the derived content hash).
"""

from __future__ import annotations

import re
from typing import Annotated, Any, Literal

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
    response: Response
    covariates: list[Covariate] = Field(default_factory=list)
    taxa: list[Taxon] | None = None
    region: list[str] | None = None
    component: str | None = None
    covt_defs: dict[str, str] | None = None
    response_definition: str | None = None
    descriptors: dict[str, Scalar | list] | None = None
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
    type: Literal["fixed_effects"] = "fixed_effects"
    parameters: dict[str, float]
    equation: str


class Specification(BaseModel):
    """One row of a parameterized set: parameter values plus optional scope."""

    model_config = ConfigDict(extra="forbid")

    parameters: dict[str, float]
    taxa: list[Taxon] | None = None
    region: list[str] | None = None
    component: str | None = None
    descriptors: dict[str, Scalar | list] | None = None


class FixedEffectsSetModel(ModelBase):
    type: Literal["fixed_effects_set"] = "fixed_effects_set"
    parameter_names: list[str]
    specifications: list[Specification]


Model = Annotated[
    FixedEffectsModel | FixedEffectsSetModel,
    Field(discriminator="type"),
]


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
    taxa: list[Taxon] | None = None

    @field_validator("year")
    @classmethod
    def _sane_year(cls, v: int) -> int:
        if v < 1000 or v > 2100:
            raise ValueError(f"implausible year {v}")
        return v


class ModelsFile(BaseModel):
    """Top-level structure of a single publication YAML file."""

    model_config = ConfigDict(extra="forbid")

    publication: Publication
    models: list[Model] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_model_names(self) -> ModelsFile:
        names = [m.name for m in self.models]
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
    equation: str | None = None
    parameter_names: list[str] | None = None
    taxa: list[Taxon] | None = None
    region: list[str] | None = None
    component: str | None = None
    covt_defs: dict[str, str] | None = None
    response_definition: str | None = None
    descriptors: dict[str, Scalar | list] | None = None
    source_file: str