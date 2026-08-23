"""Resolve model family blobs against the compiled registry.

Implements the resolution layer referenced by the family docs: run each
blob's ``select`` criteria against the flat model/spec registry built from
publication files, apply the per-blob invariants (shared response units,
exact covariate set), and report the models each blob resolves to. This is the
debugging / family-development workflow exposed as ``orc resolve``.

Selection semantics (per ``docs/families.md``):

- Criteria within a blob are **ANDed**; multiple blobs in a family are ORed.
- ``select.taxa`` matches a row if **any** of its taxon entries satisfies
  *all* specified levels; levels not specified in the select do not filter.
- A blob is a filter — it re-resolves as the registry changes.

Per-blob invariants, enforced over the rows a blob resolves to:

1. Every resolved row shares the same response *(name, units)* pair matching
   the blob's declared ``response``.
2. Every resolved row has the **exact same** covariate set, compared on
   *(name, units-or-kind)* pairs matching the blob's declared ``covariates``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from orc.families import FamilySelect, ModelBlob, ModelFamily
from orc.ingest import iter_yaml_files
from orc.records import flatten
from orc.schema import ModelsFile, Taxon

# Model kinds that can carry per-spec rows (vs a single spec_index-0 row).
_SET_KIND = "fixed_effects_set"


@dataclass
class RegistryRow:
    """One queryable model/spec row, joined from model + spec records."""

    model_id: str
    model_name: str
    model_type: str
    pub_id: str
    spec_index: int
    response_name: str
    response_units: str
    covariates: list[tuple[str, str | None]]
    taxa: list[Taxon] | None = None
    region: list[str] | None = None
    component: str | None = None
    descriptors: dict[str, object] | None = None

    def identity(self) -> str:
        """Human label for this row, e.g. ``hstix50`` or ``cuvol spec Pinus resinosa``."""
        if self.model_type != _SET_KIND:
            return self.model_name
        parts = []
        for t in self.taxa or []:
            if t.species:
                parts.append(f"{t.genus} {t.species}")
            elif t.genus:
                parts.append(t.genus)
            elif t.family:
                parts.append(t.family)
        suffix = " ".join(parts)
        return f"{self.model_name} spec {suffix}".rstrip()

    def covariate_pairs(self) -> set[tuple[str, str | None]]:
        return set(self.covariates)

    def covariate_names(self) -> set[str]:
        return {name for name, _ in self.covariates}


def build_registry(root: str | Path) -> list[RegistryRow]:
    """Build the flat registry from every publication YAML under ``root``.

    Family YAML files (top-level ``family:`` key) and other non-publication
    files are skipped; a publication file that fails schema validation is
    skipped as well (``orc ingest`` is the authority for corpus validation).
    """
    rows: list[RegistryRow] = []
    for path in iter_yaml_files(root):
        try:
            raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 - unparseable file, skip
            continue
        if not isinstance(raw, dict) or "family" in raw:
            continue
        try:
            models_file = ModelsFile.model_validate(raw)
        except Exception:  # noqa: BLE001 - not a valid publication, skip
            continue

        _, model_records, spec_records = flatten(models_file, str(path))
        models_by_id = {m.id: m for m in model_records}
        for spec in spec_records:
            model = models_by_id[spec.model_id]
            rows.append(
                RegistryRow(
                    model_id=model.id,
                    model_name=model.model_name,
                    model_type=model.model_type,
                    pub_id=model.pub_id,
                    spec_index=spec.spec_index,
                    response_name=model.response.name,
                    response_units=model.response.units,
                    covariates=[(c.name, c.units) for c in model.covariates],
                    taxa=spec.taxa,
                    region=spec.region,
                    component=spec.component,
                    descriptors=spec.descriptors,
                )
            )
    return rows


def _taxa_match(row_taxa: list[Taxon] | None, select: Taxon) -> bool:
    """True if any row taxon satisfies all levels specified by ``select``."""
    if not row_taxa:
        return False
    for t in row_taxa:
        if (
            (select.family is None or t.family == select.family)
            and (select.genus is None or t.genus == select.genus)
            and (select.species is None or t.species == select.species)
        ):
            return True
    return False


def _region_match(row_region: list[str] | None, select: list[str]) -> bool:
    if not row_region or not select:
        return False
    return bool(set(row_region) & set(select))


def _descriptors_match(row: dict[str, object] | None, select: dict[str, object]) -> bool:
    if not row:
        return False
    return all(row.get(k) == v for k, v in select.items())


def _row_matches(row: RegistryRow, select: FamilySelect) -> bool:
    if select.pub_id is not None and row.pub_id != select.pub_id:
        return False
    if select.model_id is not None and row.model_id != select.model_id:
        return False
    if select.model_name is not None and row.model_name != select.model_name:
        return False
    if select.model_set_name is not None and (
        row.model_type != _SET_KIND or row.model_name != select.model_set_name
    ):
        return False
    if select.taxa is not None and not _taxa_match(row.taxa, select.taxa):
        return False
    if select.region is not None and not _region_match(row.region, select.region):
        return False
    if select.component is not None and row.component != select.component:
        return False
    if select.descriptors is not None and not _descriptors_match(
        row.descriptors, select.descriptors
    ):
        return False
    return True


@dataclass
class BlobResult:
    blob: ModelBlob
    matched: list[RegistryRow] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


@dataclass
class ResolveResult:
    family: ModelFamily
    blobs: list[BlobResult] = field(default_factory=list)

    @property
    def errors(self) -> list[str]:
        return [f"{b.blob.id}: {e}" for b in self.blobs for e in b.errors]

    @property
    def ok(self) -> bool:
        return not self.errors


def resolve(family: ModelFamily, registry: list[RegistryRow]) -> ResolveResult:
    """Resolve every blob of ``family`` against ``registry``."""
    result = ResolveResult(family=family)
    for blob in family.model_blobs:
        matched = [r for r in registry if _row_matches(r, blob.select)]
        blob_result = BlobResult(blob=blob, matched=matched)

        if not matched:
            blob_result.errors.append("blob resolves to no models")

        _check_invariants(blob, matched, blob_result.errors)

        result.blobs.append(blob_result)
    return result


def _check_invariants(
    blob: ModelBlob, matched: list[RegistryRow], errors: list[str]
) -> None:
    """Enforce shared-response and exact-covariate invariants across ``matched``."""
    if not matched:
        return

    # Response: every row must be the blob's response name with identical units.
    response_pairs = {(r.response_name, r.response_units) for r in matched}
    if any(r.response_name != blob.response for r in matched):
        names = sorted({r.response_name for r in matched})
        errors.append(
            f"resolves to response {names} but blob declares {blob.response!r}"
        )
    elif len(response_pairs) != 1:
        errors.append(f"mixed response units across resolved models: {sorted(response_pairs)}")

    # Covariates: exact name set per row, identical (name, units) across rows.
    cov_names = [r.covariate_names() for r in matched]
    if any(names != set(blob.covariates) for names in cov_names):
        errors.append(
            f"covariates {sorted(cov_names[0])} do not match blob {sorted(blob.covariates)}"
        )
    cov_pairs = [r.covariate_pairs() for r in matched]
    if len(set(frozenset(p) for p in cov_pairs)) != 1:
        errors.append("mixed covariate units across resolved models")
