"""Ingest model YAML into a validated, content-addressed registry.

Pipeline per file:

1. parse YAML
2. validate against :class:`orc.schema.ModelsFile` (publications) or
   :class:`orc.families.ModelFamily` (family files, top-level ``family:``)
3. derive each model's 8-char content id (or cross-check one already in source)
4. flatten to one :class:`RegistryRecord` per model

Family files are validated and checked (id globally unique, id matches the
filename stem) but not resolved here; ``orc resolve`` / the parquet writer
perform resolution against the compiled registry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import yaml

from orc.families import ModelFamily
from orc.ids import content_hash
from orc.schema import Model, ModelsFile, RegistryRecord
YAML_SUFFIXES = (".yaml", ".yml")


@dataclass
class IngestError:
    path: Path
    message: str
    model_name: str | None = None

    def render(self) -> str:
        where = self.path
        if self.model_name:
            where = f"{where} (model {self.model_name!r})"
        return f"{where}: {self.message}"


@dataclass
class IngestWarning:
    path: Path
    message: str

    def render(self) -> str:
        return f"{self.path}: {self.message}"


@dataclass
class IngestResult:
    registry: list[RegistryRecord] = field(default_factory=list)
    files: list[tuple[Path, ModelsFile]] = field(default_factory=list)
    family_files: list[tuple[Path, ModelFamily]] = field(default_factory=list)
    errors: list[IngestError] = field(default_factory=list)
    warnings: list[IngestWarning] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def iter_yaml_files(root: str | Path) -> Iterator[Path]:
    """Yield candidate YAML files under ``root``, in stable order.

    Hidden directories (any path component starting with ``.``) are skipped,
    so ``.git/``, ``.venv/`` and ``.github/`` never get parsed as corpus files.
    """
    path = Path(root)
    if path.is_file():
        yield path
        return
    for p in sorted(path.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in YAML_SUFFIXES:
            continue
        if any(part.startswith(".") for part in p.relative_to(path).parts):
            continue
        yield p


def load_models_file(path: Path) -> ModelsFile:
    """Parse and schema-validate a single model YAML file.

    Raises ``ValidationError`` (yaml or pydantic) on any failure.
    """
    with path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    if not isinstance(raw, dict):
        raise ValueError("top level must be a mapping")
    return ModelsFile.model_validate(raw)


def model_id(model: Model) -> str:
    """Content-addressed id for one model, ignoring any id in source."""
    payload = model.model_dump(exclude={"id"})
    return content_hash(payload)


def ingest(root: str | Path) -> IngestResult:
    """Ingest every YAML file under ``root`` into a validated registry."""
    result = IngestResult()
    seen_ids: dict[str, list[str]] = {}
    seen_family_ids: dict[str, Path] = {}

    for path in iter_yaml_files(root):
        try:
            with path.open("r", encoding="utf-8") as fh:
                raw = yaml.safe_load(fh)
        except Exception as exc:  # noqa: BLE001 - surface every kind of failure
            result.errors.append(IngestError(path=path, message=str(exc)))
            continue
        if not isinstance(raw, dict):
            result.errors.append(IngestError(path=path, message="top level must be a mapping"))
            continue

        if "family" in raw:
            _register_family(result, raw, path, seen_family_ids)
            continue

        try:
            models_file = ModelsFile.model_validate(raw)
        except Exception as exc:  # noqa: BLE001 - surface every kind of failure
            result.errors.append(IngestError(path=path, message=str(exc)))
            continue

        result.files.append((path, models_file))

        for model in models_file.models:
            _register_model(
                result, models_file, model, path, seen_ids,
                parameters=model.parameters,
                parameter_names=None,
            )
        for model_set in models_file.model_sets:
            _register_model(
                result, models_file, model_set, path, seen_ids,
                parameters=None,
                parameter_names=list(model_set.specifications[0].parameters),
            )

    for model_id_, refs in seen_ids.items():
        if len(refs) > 1:
            result.warnings.append(
                IngestWarning(
                    path=Path("."),
                    message=f"id {model_id_} shared by content-identical models: {refs}",
                )
            )

    return result


def _register_family(
    result: IngestResult,
    raw: dict,
    path: Path,
    seen_family_ids: dict[str, Path],
) -> None:
    """Validate one family file and enforce id uniqueness + filename stem."""
    try:
        family = ModelFamily.model_validate(raw)
    except Exception as exc:  # noqa: BLE001 - surface every kind of failure
        result.errors.append(IngestError(path=path, message=str(exc)))
        return

    if path.stem != family.family.id:
        result.errors.append(
            IngestError(
                path=path,
                message=(
                    f"family id {family.family.id!r} does not match "
                    f"filename stem {path.stem!r}"
                ),
            )
        )
    if family.family.id in seen_family_ids:
        result.errors.append(
            IngestError(
                path=path,
                message=(
                    f"duplicate family id {family.family.id!r} "
                    f"(first seen in {seen_family_ids[family.family.id]})"
                ),
            )
        )
    seen_family_ids[family.family.id] = path
    result.family_files.append((path, family))


def _register_model(
    result: IngestResult,
    models_file: ModelsFile,
    model: Model,
    path: Path,
    seen_ids: dict[str, list[str]],
    *,
    parameters: dict[str, float] | None,
    parameter_names: list[str] | None,
) -> None:
    """Validate the id and append one flat registry record for ``model``."""
    computed = model_id(model)
    if model.id is not None:
        if model.id != computed:
            result.errors.append(
                IngestError(
                    path=path,
                    model_name=model.name,
                    message=f"id {model.id!r} does not match content hash {computed!r}",
                )
            )
    else:
        model.id = computed

    record = RegistryRecord(
        id=computed,
        pub_id=models_file.publication.key,
        pub_year=models_file.publication.year,
        model_name=model.name,
        model_type=model.type,
        response=model.response,
        covariates=model.covariates,
        parameters=parameters,
        prediction_function=model.prediction_function,
        parameter_names=parameter_names,
        taxa=model.taxa,
        region=model.region,
        component=model.component,
        covt_defs=model.covt_defs,
        response_definition=model.response_definition,
        description=model.description,
        descriptors=model.descriptors,
        source_file=str(path),
    )
    result.registry.append(record)
    seen_ids.setdefault(computed, []).append(
        f"{models_file.publication.key}/{model.name}"
    )