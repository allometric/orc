"""Schema for curated model families.

A model family is a labelled selection over the compiled registry: it stores
no model content, only a description plus selection rules (model blobs) that
resolve to concrete models in ``publications``/``models``/``model_specs``.
See ``model_families_plan.md`` for the full design; this module implements the
YAML schema only. Resolution against the registry (blob matching, invariant
checks, the compiled membership table) is a later ingest-layer step.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from orc.ids import is_valid_id
from orc.schema import Scalar, Taxon


class FamilySelect(BaseModel):
    """Selection criteria for one blob; criteria are ANDed together.

    At least one criterion must be present — an empty select would match every
    model and is treated as an authoring error.
    """

    model_config = ConfigDict(extra="forbid")

    pub_id: str | None = None
    model_id: str | None = None
    model_set_name: str | None = None
    model_name: str | None = None
    taxa: Taxon | None = None
    region: list[str] | None = None
    component: str | None = None
    descriptors: dict[str, Scalar | list] | None = None

    @model_validator(mode="after")
    def _at_least_one_criterion(self) -> FamilySelect:
        if not any(
            (
                self.pub_id,
                self.model_id,
                self.model_set_name,
                self.model_name,
                self.taxa,
                self.region,
                self.component,
                self.descriptors,
            )
        ):
            raise ValueError("select needs at least one criterion")
        return self

    @model_validator(mode="after")
    def _valid_model_id(self) -> FamilySelect:
        if self.model_id is not None and not is_valid_id(self.model_id):
            raise ValueError(
                f"model_id must be an 8-char hex string, got {self.model_id!r}"
            )
        return self


class ModelBlob(BaseModel):
    """One selection rule; resolves to the models matching ``select``.

    ``id`` is the blob's short name, leading the blob definition and unique
    within the family; ``label`` is an optional human-readable provenance.
    ``response`` and ``covariates`` are declared here as bare names. The
    resolution layer later checks that every model this blob resolves to
    agrees on the full (name, units) pair for the response and on the exact
    set of (name, units-or-kind) pairs for covariates.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    label: str | None = None
    response: str = Field(min_length=1)
    covariates: list[str]
    select: FamilySelect


_CRAN_ROLES = {"aut", "cre", "ctb", "cph", "fnd", "rev", "ths", "trc"}


class Maintainer(BaseModel):
    """One family maintainer.

    Families are maintained by users of the ``allometric`` ecosystem, and
    authorship is tracked in the manner of R packages / CRAN: a required
    ``name`` plus optional contact, affiliation, and role metadata.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    email: str | None = None
    orcid: str | None = None
    institution: str | None = None
    role: str | list[str] | None = None

    @model_validator(mode="after")
    def _valid_roles(self) -> Maintainer:
        roles = [self.role] if isinstance(self.role, str) else (self.role or [])
        bad = [r for r in roles if r not in _CRAN_ROLES]
        if bad:
            raise ValueError(f"unknown CRAN role(s): {bad}")
        return self


class FamilyMeta(BaseModel):
    """The ``family:`` block: metadata only.

    Response and covariate structure is deliberately *not* declared here —
    families are loose, and each blob carries its own ``response`` and
    ``covariates`` (see :class:`ModelBlob`).

    ``pub_id`` optionally names the publication a family is curated from.
    It is provenance metadata only: it does not constrain resolution (blobs
    still select independently via ``FamilySelect.pub_id``), but it lets a
    family that is essentially "the curated set from publication X" declare
    that link explicitly and joinable in the compiled output.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    maintainers: list[Maintainer] = Field(min_length=1)
    pub_id: str | None = None
    descriptors: dict[str, Scalar | list] | None = None


class ModelFamily(BaseModel):
    """Top-level structure of a single model family YAML file.

    One family per file, named ``model_families/<family.id>.yaml``. Global
    uniqueness of ``family.id`` and the filename-stem match are checked by the
    ingest layer, which sees all files at once.
    """

    model_config = ConfigDict(extra="forbid")

    family: FamilyMeta
    model_blobs: list[ModelBlob] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_blob_ids(self) -> ModelFamily:
        ids = [b.id for b in self.model_blobs]
        if len(ids) != len(set(ids)):
            raise ValueError(f"model blob ids must be unique within a family: {ids}")
        return self
