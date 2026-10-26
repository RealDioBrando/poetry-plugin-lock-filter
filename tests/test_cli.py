from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import tomlkit

from poetry_plugin_lock_filter.cli import main
from poetry_plugin_lock_filter.plugin import FilterLockApplicationPlugin


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_lock(self) -> None:
        document = tomlkit.document()
        packages = tomlkit.parse("[[package]]\n")["package"]
        packages.clear()

        linux = tomlkit.table()
        linux["name"] = "linux-package"
        linux["version"] = "1.0"
        linux["groups"] = ["main"]
        linux["markers"] = 'sys_platform == "linux"'
        packages.append(linux)

        windows = tomlkit.table()
        windows["name"] = "windows-package"
        windows["version"] = "2.0"
        windows["groups"] = ["main"]
        windows["markers"] = 'sys_platform == "win32"'
        packages.append(windows)

        document["package"] = packages
        metadata = tomlkit.table()
        metadata["lock-version"] = "2.1"
        document["metadata"] = metadata
        (self.root / "poetry.lock").write_text(
            tomlkit.dumps(document), encoding="utf-8"
        )

    def test_cli_writes_marker_specific_lock_and_report(self) -> None:
        self.write_lock()
        output = self.root / "filtered.lock"
        report = self.root / "report.json"
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            self.assertEqual(
                main(
                    [
                        "--project",
                        str(self.root),
                        "--output",
                        str(output),
                        "--preset",
                        "linux-aarch64-cp311",
                        "--report",
                        str(report),
                    ]
                ),
                0,
            )

        filtered = tomlkit.parse(output.read_text(encoding="utf-8"))
        self.assertEqual(
            [package["name"] for package in filtered["package"]],
            ["linux-package"],
        )
        parsed_report = json.loads(report.read_text(encoding="utf-8"))
        self.assertEqual(parsed_report["included_packages"], ["linux-package"])
        self.assertEqual(
            parsed_report["excluded_packages"][0]["package"],
            "windows-package",
        )

    def test_plugin_registers_filter_lock_command(self) -> None:
        plugin = FilterLockApplicationPlugin()
        self.assertEqual(
            [command.name for command in plugin.commands],
            ["filter-lock"],
        )


if __name__ == "__main__":
    unittest.main()
