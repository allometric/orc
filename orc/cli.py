"""Command-line interface for orc."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from orc import __version__
from orc.ingest import IngestResult, ingest, iter_yaml_files, write_registry_jsonl


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
    if args.registry:
        write_registry_jsonl(result, args.registry)
        print(f"registry: wrote {len(result.registry)} records -> {args.registry}")
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
        "--registry",
        type=Path,
        default=None,
        help="write the compiled registry as JSONL to this path",
    )
    ingest_p.set_defaults(func=_cmd_ingest)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())