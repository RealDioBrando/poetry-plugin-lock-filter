"""Poetry command for marker-specific lock filtering."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from cleo.helpers import option
from poetry.console.commands.command import Command

if TYPE_CHECKING:
    from cleo.io.inputs.option import Option

from poetry_plugin_lock_filter.core import (
    PRESETS,
    LockFilterError,
    build_environment,
    filter_lock_file,
    write_report,
)


class FilterLockCommand(Command):
    name = "filter-lock"
    description = "Create a marker-specific Poetry lock file."

    options: ClassVar[list[Option]] = [
        option(
            "output",
            "o",
            "Output lock file (default: poetry.target.lock)",
            flag=False,
        ),
        option(
            "preset",
            None,
            "Target environment preset (default: linux-aarch64-cp311)",
            flag=False,
            default="linux-aarch64-cp311",
        ),
        option(
            "env",
            None,
            "Override a marker environment value, KEY=VALUE (repeatable)",
            flag=False,
            multiple=True,
        ),
        option(
            "group",
            None,
            "Dependency group to retain (default: main)",
            flag=False,
            default="main",
        ),
        option(
            "include-optional",
            None,
            "Keep optional packages",
        ),
        option(
            "report",
            None,
            "Write a JSON filtering report",
            flag=False,
        ),
        option(
            "no-check",
            None,
            "Do not require a fresh poetry.lock file",
        ),
    ]

    def handle(self) -> int:
        preset = str(self.option("preset"))
        if preset not in PRESETS:
            self.line_error(
                f"<error>Unknown preset {preset!r}. Expected one of: "
                f"{', '.join(sorted(PRESETS))}</error>"
            )
            return 1

        environment_overrides = self._parse_environment_overrides()
        if environment_overrides is None:
            return 1

        locker = self.poetry.locker
        if not locker.is_locked():
            self.line_error("<error>poetry.lock was not found.</error>")
            return 1

        if not self.option("no-check") and not locker.is_fresh():
            self.line_error(
                "<error>poetry.lock is not fresh. Run `poetry lock` first.</error>"
            )
            return 1

        project_root = self.poetry.file.path.parent
        output = self._project_path(
            self.option("output") or "poetry.target.lock", project_root
        )
        report_path = (
            self._project_path(self.option("report"), project_root)
            if self.option("report")
            else None
        )

        try:
            environment = build_environment(preset, environment_overrides)
            report = filter_lock_file(
                locker.lock,
                output,
                environment,
                group=str(self.option("group")),
                include_optional=bool(self.option("include-optional")),
            )
        except LockFilterError as error:
            self.line_error(f"<error>{error}</error>")
            return 1

        if report_path is not None:
            write_report(report_path, report)

        self.info(f"Filtered lock written to {output}")
        self.line(
            f"Included {report['included_count']} package(s); "
            f"excluded {report['excluded_count']} package(s)."
        )
        return 0

    def _parse_environment_overrides(self) -> dict[str, str] | None:
        overrides: dict[str, str] = {}
        values = self.option("env")
        if values is None:
            return overrides
        if isinstance(values, str):
            values = [values]

        for value in values:
            key, separator, environment_value = str(value).partition("=")
            if not separator or not key.strip():
                self.line_error(
                    f"<error>Invalid environment override {value!r}. Expected KEY=VALUE.</error>"
                )
                return None
            overrides[key.strip()] = environment_value
        return overrides

    @staticmethod
    def _project_path(value: str, project_root: Path) -> Path:
        path = Path(value)
        return path if path.is_absolute() else project_root / path
