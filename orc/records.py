"""Canonical flat records (Layer A) for the compiled storage layer.

Three relational tables, format-agnostic (the parquet/duckdb writers consume
these). Consumers are expected to *join* the tables rather than consume a
single denormalized row, so each table carries only its own scope:

- ``PublicationRecord`` — one row per publication (BibTeX + pub descriptors).
- ``ModelRecord`` — one row per model set / single model (set-level scope).
- ``ModelSpecRecord`` — one row per specification (per-spec scope, resolved by
  fallback to the set when the spec doesn't declare its own).

Flattening rule: a ``fixed_effects`` model yields one spec row (spec_index 0);
a ``fixed_effects_set`` yields one row per ``specifications`` entry. Content
hash ``id`` stays at the set granularity; ``spec_index`` disambiguates rows.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from orc.families import Maintainer, ModelFamily
from orc.ingest import model_id
from orc.schema import (
    Covariate,
    FixedEffectsModel,
    FixedEffectsSetModel,
    Model,
    ModelsFile,
    Response,
    Taxon,
)

Scalar = str | int | float | bool


class Parameter(BaseModel):
    """One named parameter value in a spec row (list-of-struct form)."""

    model_config = ConfigDict(extra="forbid")

    name: str
    value: float


class PublicationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pub_id: str
    bibtype: str
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


class ModelRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    pub_id: str
    model_name: str
    model_type: str
    response: Response
    covariates: list[Covariate]
    prediction_function: str
    covt_defs: dict[str, str] | None = None
    response_definition: str | None = None
    description: str | None = None
    notes: str | None = None
    taxa: list[Taxon] | None = None
    region: list[str] | None = None
    component: str | None = None
    descriptors: dict[str, Scalar | list] | None = None
    source_file: str


class ModelSpecRecord(BaseModel):
    """One queryable spec row. Scope is fallback-resolved from the set."""

    model_config = ConfigDict(extra="forbid")

    model_id: str
    spec_index: int
    parameters: list[Parameter]
    taxa: list[Taxon] | None = None
    region: list[str] | None = None
    component: str | None = None
    descriptors: dict[str, Scalar | list] | None = None


class FamilyRecord(BaseModel):
    """One row per model family (family-level metadata)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    description: str
    maintainers: list[Maintainer]
    pub_id: str | None = None
    descriptors: dict[str, Scalar | list] | None = None


class FamilyBlobRecord(BaseModel):
    """One row per blob: the selection rule, with select criteria flattened."""

    model_config = ConfigDict(extra="forbid")

    family_id: str
    blob_id: str
    label: str | None = None
    response: str
    covariates: list[str]
    select_pub_id: str | None = None
    select_model_id: str | None = None
    select_model_set_name: str | None = None
    select_model_name: str | None = None
    select_taxa: Taxon | None = None
    select_region: list[str] | None = None
    select_component: str | None = None
    select_descriptors: dict[str, Scalar | list] | None = None


class FamilyMemberRecord(BaseModel):
    """One pinned membership row: blob -> resolved model/spec."""

    model_config = ConfigDict(extra="forbid")

    family_id: str
    blob_id: str
    model_id: str
    spec_index: int


def build_publication_record(models_file: ModelsFile) -> PublicationRecord:
    pub = models_file.publication
    return PublicationRecord(
        pub_id=pub.key,
        bibtype=pub.bibtype,
        title=pub.title,
        author=pub.author,
        year=pub.year,
        number=pub.number,
        institution=pub.institution,
        journal=pub.journal,
        volume=pub.volume,
        pages=pub.pages,
        doi=pub.doi,
        url=pub.url,
        publisher=pub.publisher,
        address=pub.address,
        month=pub.month,
        note=pub.note,
        school=pub.school,
        organization=pub.organization,
        series=pub.series,
        booktitle=pub.booktitle,
        editor=pub.editor,
        howpublished=pub.howpublished,
        edition=pub.edition,
        descriptors=pub.descriptors,
    )


def build_model_record(models_file: ModelsFile, model: Model, source_file: str) -> ModelRecord:
    return ModelRecord(
        id=model.id,
        pub_id=models_file.publication.key,
        model_name=model.name,
        model_type=model.type,
        response=model.response,
        covariates=model.covariates,
        prediction_function=model.prediction_function,
        covt_defs=model.covt_defs,
        response_definition=model.response_definition,
        description=model.description,
        notes=model.notes,
        taxa=model.taxa,
        region=model.region,
        component=model.component,
        descriptors=model.descriptors,
        source_file=source_file,
    )


def _fallback(spec_value: Any, model_value: Any) -> Any:
    """Return the spec's declared value, else the model/set-level value."""
    return spec_value if spec_value is not None else model_value


def build_spec_records(model: Model, model_id: str) -> list[ModelSpecRecord]:
    """Yield one ``ModelSpecRecord`` per specification (0 for single models)."""
    if isinstance(model, FixedEffectsModel):
        return [
            ModelSpecRecord(
                model_id=model_id,
                spec_index=0,
                parameters=[
                    Parameter(name=k, value=v) for k, v in model.parameters.items()
                ],
                taxa=model.taxa,
                region=model.region,
                component=model.component,
                descriptors=model.descriptors,
            )
        ]

    if isinstance(model, FixedEffectsSetModel):
        return [
            ModelSpecRecord(
                model_id=model_id,
                spec_index=i,
                parameters=[Parameter(name=k, value=v) for k, v in spec.parameters.items()],
                taxa=_fallback(spec.taxa, model.taxa),
                region=_fallback(spec.region, model.region),
                component=_fallback(spec.component, model.component),
                descriptors=_fallback(spec.descriptors, model.descriptors),
            )
            for i, spec in enumerate(model.specifications)
        ]

    raise TypeError(f"unhandled model kind: {type(model).__name__}")


def _ensure_id(model: Model) -> str:
    """Return the model's content-hash id, assigning it if not in source."""
    if model.id is None:
        model.id = model_id(model)
    return model.id


def flatten(models_file: ModelsFile, source_file: str) -> tuple[PublicationRecord, list[ModelRecord], list[ModelSpecRecord]]:
    """Build the three record lists from one validated ``ModelsFile``."""
    pub_record = build_publication_record(models_file)
    model_records: list[ModelRecord] = []
    spec_records: list[ModelSpecRecord] = []
    for model in list(models_file.models) + list(models_file.model_sets):
        model_id_ = _ensure_id(model)
        model_records.append(build_model_record(models_file, model, source_file))
        spec_records.extend(build_spec_records(model, model_id_))
    return pub_record, model_records, spec_records


def build_family_record(family: ModelFamily) -> FamilyRecord:
    """One ``FamilyRecord`` from a validated family file."""
    meta = family.family
    return FamilyRecord(
        id=meta.id,
        title=meta.title,
        description=meta.description,
        maintainers=meta.maintainers,
        pub_id=meta.pub_id,
        descriptors=meta.descriptors,
    )


def build_family_blob_records(family: ModelFamily) -> list[FamilyBlobRecord]:
    """One ``FamilyBlobRecord`` per blob, select criteria flattened."""
    records: list[FamilyBlobRecord] = []
    for b in family.model_blobs:
        sel = b.select
        records.append(
            FamilyBlobRecord(
                family_id=family.family.id,
                blob_id=b.id,
                label=b.label,
                response=b.response,
                covariates=b.covariates,
                select_pub_id=sel.pub_id,
                select_model_id=sel.model_id,
                select_model_set_name=sel.model_set_name,
                select_model_name=sel.model_name,
                select_taxa=sel.taxa,
                select_region=sel.region,
                select_component=sel.component,
                select_descriptors=sel.descriptors,
            )
        )
    return records
