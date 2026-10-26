"""Standalone command-line interface for marker-specific Poetry lock filtering."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from poetry_plugin_lock_filter.core import (
    PRESETS,
    LockFilterError,
    build_environment,
    filter_lock_file,
    write_report,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="poetry-lock-filter",
        description="Create a marker-specific Poetry lock file.",
    )
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--lock", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--preset",
        choices=sorted(PRESETS),
        default="linux-aarch64-cp311",
    )
    parser.add_argument(
        "--env",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="override a marker environment value; repeatable",
    )
    parser.add_argument("--group", default="main")
    parser.add_argument("--include-optional", action="store_true")
    parser.add_argument("--report", type=Path)
    return parser


def _parse_environment_overrides(values: list[str]) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for value in values:
        key, separator, environment_value = value.partition("=")
        if not separator or not key.strip():
            raise argparse.ArgumentTypeError(
                f"Expected KEY=VALUE environment override, got {value!r}"
            )
        overrides[key.strip()] = environment_value
    return overrides


def _resolve(path: Path, project: Path) -> Path:
    return path if path.is_absolute() else project / path


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    project = args.project.resolve()

    try:
        overrides = _parse_environment_overrides(args.env)
        lock = args.lock.resolve() if args.lock else (project / "poetry.lock").resolve()
        output = (
            _resolve(args.output, project)
            if args.output
            else project / "poetry.target.lock"
        )
        report_path = _resolve(args.report, project) if args.report else None

        environment = build_environment(args.preset, overrides)
        report = filter_lock_file(
            lock,
            output,
            environment,
            group=args.group,
            include_optional=args.include_optional,
        )
    except (LockFilterError, argparse.ArgumentTypeError) as error:
        parser.exit(1, f"ERROR: {error}\n")

    if report_path is not None:
        write_report(report_path, report)

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
