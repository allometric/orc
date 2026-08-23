"""Command-line interface for orc."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from orc import __version__
from orc.families import ModelFamily
from orc.ingest import IngestResult, ingest, iter_yaml_files
from orc.resolve import build_registry, resolve
from orc.writer import write_parquet


def _print_result(result: IngestResult, files: int) -> None:
    print(f"files:   {files}")
    print(f"models:  {len(result.registry)}")
    for warn in result.warnings:
        print(f"warning: {warn.render()}")
    for err in result.errors:
        print(f"error:   {err.render()}")


def _cmd_ingest(args: argparse.Namespace) -> int:
    result = ingest(args.path)
    files = sum(1 for _ in iter_yaml_files(args.path))
    _print_result(result, files)
    if args.parquet:
        counts = write_parquet(result.files, args.parquet)
        print("parquet:  " + ", ".join(f"{k}={v}" for k, v in counts.items()))
        print(f"          -> {args.parquet}/")
    return 0 if result.ok else 1


def _cmd_resolve(args: argparse.Namespace) -> int:
    with args.family.open("r", encoding="utf-8") as fh:
        family = ModelFamily.model_validate(yaml.safe_load(fh))
    registry = build_registry(args.registry)
    result = resolve(family, registry)

    print(f"family: {family.family.id}")
    print()
    total = 0
    for blob_result in result.blobs:
        label = blob_result.blob.label or ""
        print(f'{blob_result.blob.id}  "{label}"')
        for row in blob_result.matched:
            total += 1
            covs = ", ".join(name for name, _ in row.covariates)
            print(
                f"  -> {row.identity()} ({row.pub_id})  "
                f"response {row.response_name} [{row.response_units}], "
                f"covariates [{covs}]"
            )
        for err in blob_result.errors:
            print(f"  !! {err}")
    print()
    if result.ok:
        print(f"{len(result.blobs)} blobs, {total} resolved models; invariants ok")
    else:
        print(f"{len(result.blobs)} blobs, {total} resolved models; {len(result.errors)} error(s)")
    return 0 if result.ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="orc", description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    ingest_p = sub.add_parser("ingest", help="validate a directory of model YAML")
    ingest_p.add_argument(
        "path",
        type=Path,
        nargs="?",
        default=Path("."),
        help="YAML file or directory to ingest (default: current directory)",
    )
    ingest_p.add_argument(
        "--parquet",
        type=Path,
        default=None,
        help="write publications/models/model_specs parquet tables to this directory",
    )
    ingest_p.set_defaults(func=_cmd_ingest)

    resolve_p = sub.add_parser(
        "resolve", help="resolve a model family's blobs against the compiled registry"
    )
    resolve_p.add_argument(
        "family",
        type=Path,
        help="model family YAML file (e.g. model_families/<family_id>.yaml)",
    )
    resolve_p.add_argument(
        "registry",
        type=Path,
        nargs="?",
        default=Path("."),
        help="publication YAML file/directory to build the registry from (default: current directory)",
    )
    resolve_p.set_defaults(func=_cmd_resolve)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())