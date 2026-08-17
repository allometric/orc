"""Ingest model YAML into a validated, content-addressed registry.

Pipeline per file:

1. parse YAML
2. validate against :class:`orc.schema.ModelsFile`
3. derive each model's 8-char content id (or cross-check one already in source)
4. cross-validate parameterized sets (``parameter_names`` vs. spec rows)
5. flatten to one :class:`RegistryRecord` per model
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import yaml

from orc.ids import content_hash
from orc.schema import (
    FixedEffectsModel,
    FixedEffectsSetModel,
    Model,
    ModelsFile,
    RegistryRecord,
)

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
    errors: list[IngestError] = field(default_factory=list)
    warnings: list[IngestWarning] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def iter_yaml_files(root: str | Path) -> Iterator[Path]:
    """Yield candidate YAML files under ``root``, in stable order."""
    path = Path(root)
    if path.is_file():
        yield path
        return
    for p in sorted(path.rglob("*")):
        if p.is_file() and p.suffix.lower() in YAML_SUFFIXES:
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


def _validate_set(model: FixedEffectsSetModel) -> list[str]:
    """Cross-check a set's parameter_names against every specification row."""
    problems: list[str] = []
    if not model.parameter_names:
        problems.append("parameter_names must not be empty")
    for i, spec in enumerate(model.specifications):
        unknown = sorted(set(spec.parameters) - set(model.parameter_names))
        if unknown:
            problems.append(
                f"specification {i} uses parameters not in parameter_names: {unknown}"
            )
    return problems


def ingest(root: str | Path) -> IngestResult:
    """Ingest every YAML file under ``root`` into a validated registry."""
    result = IngestResult()
    seen_ids: dict[str, list[str]] = {}

    for path in iter_yaml_files(root):
        try:
            models_file = load_models_file(path)
        except Exception as exc:  # noqa: BLE001 - surface every kind of failure
            result.errors.append(IngestError(path=path, message=str(exc)))
            continue

        for model in models_file.models:
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

            if isinstance(model, FixedEffectsSetModel):
                for problem in _validate_set(model):
                    result.errors.append(
                        IngestError(path=path, model_name=model.name, message=problem)
                    )

            record = RegistryRecord(
                id=computed,
                pub_id=models_file.publication.key,
                pub_year=models_file.publication.year,
                model_name=model.name,
                model_type=model.type,
                response=model.response,
                covariates=model.covariates,
                parameters=(
                    model.parameters if isinstance(model, FixedEffectsModel) else None
                ),
                equation=(
                    model.equation if isinstance(model, FixedEffectsModel) else None
                ),
                parameter_names=(
                    model.parameter_names
                    if isinstance(model, FixedEffectsSetModel)
                    else None
                ),
                taxa=model.taxa,
                region=model.region,
                component=model.component,
                covt_defs=model.covt_defs,
                response_definition=model.response_definition,
                descriptors=model.descriptors,
                source_file=str(path),
            )
            result.registry.append(record)
            seen_ids.setdefault(computed, []).append(
                f"{models_file.publication.key}/{model.name}"
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


def write_registry_jsonl(result: IngestResult, out: str | Path) -> None:
    """Dump the registry as newline-delimited JSON (a cheap Parquet precursor)."""
    with open(out, "w", encoding="utf-8") as fh:
        for record in result.registry:
            fh.write(json.dumps(record.model_dump(), ensure_ascii=False) + "\n")