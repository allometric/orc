#!/usr/bin/env python3
"""One-off migration step 2 of 3: map harvested JSON back to v4 YAML.

Reads the neutral JSON produced by ``scripts/harvest.R`` and writes one YAML
file per publication that conforms to the ``orc`` schema. Flattened model
records are grouped back into ``fixed_effects`` vs ``fixed_effects_set`` based
on shared response/covariates/prediction_function, and descriptors that are
constant
across a whole publication are hoisted into the ``publication`` block.

Like harvest.R, this is a THROWAWAY migration tool, kept in the repo only so
the migration is reproducible. The ``orc`` package itself is the long-term
replacement.

Usage:
  python3 scripts/convert.py <json_dir> <out_dir>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from orc.ingest import ingest

CITATION_FIELDS = [
    "number", "institution", "journal", "volume", "pages", "doi", "url",
    "publisher", "address", "month", "note", "school", "organization",
    "series", "booktitle", "editor", "howpublished", "edition",
]


class Flow:
    """Marker: emit this subtree as single-line flow style (compact tables)."""

    def __init__(self, obj):
        self.obj = obj


class CompactDumper(yaml.SafeDumper):
    pass


def _node(dumper, obj, flow):
    if isinstance(obj, Flow):
        return _node(dumper, obj.obj, True)
    if isinstance(obj, dict):
        pairs = [(dumper.represent_data(k), _node(dumper, v, flow))
                 for k, v in obj.items()]
        return yaml.nodes.MappingNode(
            "tag:yaml.org,2002:map", pairs, flow_style=flow
        )
    if isinstance(obj, list):
        items = [_node(dumper, i, flow) for i in obj]
        return yaml.nodes.SequenceNode(
            "tag:yaml.org,2002:seq", items, flow_style=flow
        )
    return dumper.represent_data(obj)


CompactDumper.add_representer(Flow, lambda dumper, data: _node(dumper, data.obj, True))


def dedupe_specs(specs: list[dict]) -> list[dict]:
    """Nest specs: merge rows with identical scope, unioning their taxa.

    Lossless — a row is ``{parameters, [taxa], [region], [component],
    [descriptors]}``; rows that differ only in taxa collapse to one block
    listing all taxa.
    """
    groups: list[dict] = []
    index: dict[str, int] = {}
    for spec in specs:
        taxa = spec.get("taxa") or []
        scope = {k: v for k, v in spec.items() if k != "taxa"}
        key = json.dumps(scope, sort_keys=True, default=str)
        if key not in index:
            index[key] = len(groups)
            groups.append(scope)
        merged = groups[index[key]]
        if taxa:
            existing = merged.setdefault("taxa", [])
            for t in taxa:
                if t not in existing:
                    existing.append(t)
    return groups


def _stable(value) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def normalize_covariates(covs) -> list[dict]:
    if isinstance(covs, dict):
        return [
            {"name": k, "unit": (v or {}).get("unit", v) if isinstance(v, dict) else v}
            for k, v in covs.items()
        ]
    return list(covs)


def clean_parameters(params: dict) -> dict:
    """Drop missing/non-numeric parameter estimates (NA in source CSVs)."""
    out: dict = {}
    for k, v in params.items():
        if v is None:
            continue
        try:
            out[k] = float(v)
        except (TypeError, ValueError):
            continue
    return out


def clean_descriptors(record: dict) -> dict:
    params = set(record.get("parameters", {}))
    descs = record.get("descriptors", {}) or {}
    if isinstance(descs, list):
        descs = {}
    return {k: v for k, v in descs.items() if k not in params and v is not None}


def normalize_covdefs(covdefs) -> list[dict]:
    if isinstance(covdefs, dict):
        return [
            {"name": k, **({} if v is None else {"definition": v.get("definition", v) if isinstance(v, dict) else v})}
            for k, v in covdefs.items()
        ]
    return list(covdefs)


def group_key(record: dict) -> tuple:
    covs = tuple((c["name"], c["unit"]) for c in normalize_covariates(record.get("covariates", [])))
    covdefs = tuple(
        sorted((d["name"], d["definition"]) for d in normalize_covdefs(record.get("covariate_definitions", [])))
    )
    return (
        record["response"]["name"],
        record["response"]["unit"],
        covs,
        record.get("prediction_function", ""),
        covdefs,
        record.get("response_definition", ""),
    )


def split_scope(record: dict, pub_level: set[str], pub_taxa) -> tuple[list | None, dict]:
    """Return (taxa, rest-of-model-descriptors) after removing pub-constant scope."""
    descs = clean_descriptors(record)
    model_descs = {k: v for k, v in descs.items() if k not in pub_level}
    model_descs.pop("taxa", None)

    taxa = descs.get("taxa")
    if taxa is None or _stable(taxa) == _stable(pub_taxa):
        taxa = None
    return taxa, model_descs


def scope_to_fields(taxa: list | None, model_descs: dict) -> dict:
    """Map leftover model-level scope into typed fields + generic descriptors."""
    out: dict = {}
    if taxa:
        out["taxa"] = taxa
    if "region" in model_descs:
        region = model_descs.pop("region")
        out["region"] = region if isinstance(region, list) else [region]
    if "component" in model_descs:
        out["component"] = model_descs.pop("component")
    if model_descs:
        out["descriptors"] = model_descs
    return out


def build_publication(pub: dict, pub_level_descs: dict, pub_taxa: list | None) -> dict:
    cit = pub["citation"]
    out: dict = {
        "key": pub["key"],
        "bibtype": cit["bibtype"],
        "title": cit["title"],
        "author": cit["author"],
        "year": cit["year"],
    }
    for f in CITATION_FIELDS:
        if cit.get(f) not in (None, ""):
            out[f] = cit[f]
    if pub_level_descs:
        out["descriptors"] = pub_level_descs
    if pub_taxa:
        out["taxa"] = pub_taxa
    return out


def build_models(groups: list[list[dict]], pub_level: set[str], pub_taxa) -> list[dict]:
    models: list[dict] = []
    name_counts: dict[str, int] = {}

    def flow_taxa(taxa: list) -> list:
        return [Flow(t) for t in taxa]

    for records in groups:
        base = records[0]["response"]["name"]
        name_counts[base] = name_counts.get(base, 0) + 1
        name = base if name_counts[base] == 1 else f"{base}_{name_counts[base]}"

        resp = records[0]["response"]
        covs = normalize_covariates(records[0].get("covariates", []))
        common: dict = {
            "name": name,
            "type": "fixed_effects",
            "response": Flow({resp["name"]: resp["unit"]}),
            "covariates": Flow({c["name"]: c["unit"] for c in covs}),
        }
        if records[0].get("covariate_definitions"):
            common["covt_defs"] = Flow({
                d["name"]: d["definition"]
                for d in normalize_covdefs(records[0]["covariate_definitions"])
            })
        if records[0].get("response_definition"):
            common["response_definition"] = records[0]["response_definition"]

        if len(records) == 1:
            record = records[0]
            taxa, model_descs = split_scope(record, pub_level, pub_taxa)
            common["type"] = "fixed_effects"
            common["parameters"] = Flow(clean_parameters(record["parameters"]))
            common["prediction_function"] = record["prediction_function"]
            scope = scope_to_fields(taxa, model_descs)
            if scope.get("taxa"):
                scope["taxa"] = [Flow(t) for t in scope["taxa"]]
            if scope.get("descriptors"):
                scope["descriptors"] = Flow(scope["descriptors"])
            common.update(scope)
            models.append(common)
            continue

        common["type"] = "fixed_effects_set"
        common["prediction_function"] = records[0]["prediction_function"]
        plain_specs = []
        for record in records:
            taxa, model_descs = split_scope(record, pub_level, pub_taxa)
            spec: dict = {"parameters": clean_parameters(record["parameters"])}
            spec.update(scope_to_fields(taxa, model_descs))
            plain_specs.append(spec)
        common["specifications"] = [Flow(s) for s in dedupe_specs(plain_specs)]
        models.append(common)

    return models


def convert_pub(data: dict) -> dict:
    records = [dict(r) for r in data["models"]]

    all_descs = [clean_descriptors(r) for r in records]
    all_keys = {k for d in all_descs for k in d}

    def constant(key: str) -> bool:
        vals = [_stable(d[key]) for d in all_descs if key in d]
        return len(vals) == len(all_descs) and len(set(vals)) == 1

    pub_level = {k for k in all_keys if constant(k)}
    pub_level_descs = {k: all_descs[0][k] for k in pub_level if k != "taxa"}

    pub_taxa = all_descs[0].get("taxa") if "taxa" in pub_level else None

    groups: list[list[dict]] = []
    seen: dict[tuple, int] = {}
    for record in records:
        key = group_key(record)
        if key not in seen:
            seen[key] = len(groups)
            groups.append([])
        groups[seen[key]].append(record)

    return {
        "publication": build_publication(data["pub"], pub_level_descs, pub_taxa),
        "models": build_models(groups, pub_level, pub_taxa),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("json_dir", type=Path)
    parser.add_argument("out_dir", type=Path)
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    for path in sorted(args.json_dir.glob("*.json")):
        data = json.loads(path.read_text())
        yaml_doc = convert_pub(data)
        out_path = args.out_dir / f"{data['pub']['key']}.yaml"
        out_path.write_text(
            yaml.dump(
                yaml_doc,
                Dumper=CompactDumper,
                sort_keys=False,
                allow_unicode=True,
                width=1 << 20,
            )
        )
        n += 1

    result = ingest(args.out_dir)
    for warn in result.warnings:
        print(f"warning: {warn.render()}")
    for err in result.errors:
        print(f"error:   {err.render()}")
    print(f"converted {n} publications -> {args.out_dir}; "
          f"{len(result.registry)} models, {len(result.errors)} errors")
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())