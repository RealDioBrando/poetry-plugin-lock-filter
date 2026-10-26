from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import tomlkit

from poetry_plugin_lock_filter.core import (
    build_environment,
    filter_lock_file,
    marker_applies,
)


class CoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.environment = build_environment("linux-aarch64-cp311", {})

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_lock(self, packages: list[dict]) -> Path:
        document = tomlkit.document()
        package_array = tomlkit.parse("[[package]]\n")["package"]
        package_array.clear()
        for package in packages:
            package_array.append(package)
        document["package"] = package_array

        metadata = tomlkit.table()
        metadata["lock-version"] = "2.1"
        metadata["python-versions"] = ">=3.11,<3.12"
        metadata["content-hash"] = "test-hash"
        document["metadata"] = metadata

        path = self.root / "poetry.lock"
        path.write_text(tomlkit.dumps(document), encoding="utf-8")
        return path

    def test_marker_applies_to_string_and_group_tables(self) -> None:
        self.assertTrue(
            marker_applies("sys_platform == 'linux'", self.environment, "main")
        )
        self.assertFalse(
            marker_applies("sys_platform == 'win32'", self.environment, "main")
        )
        self.assertTrue(
            marker_applies(
                {"main": "platform_machine == 'aarch64'"},
                self.environment,
                "main",
            )
        )
        self.assertFalse(
            marker_applies(
                {"main": "platform_machine == 'x86_64'"},
                self.environment,
                "main",
            )
        )

    def test_filters_by_marker_group_and_optional(self) -> None:
        lock = self.write_lock(
            [
                {
                    "name": "linux-package",
                    "version": "1.0",
                    "groups": ["main"],
                    "markers": "sys_platform == 'linux'",
                },
                {
                    "name": "windows-package",
                    "version": "2.0",
                    "groups": ["main"],
                    "markers": "sys_platform == 'win32'",
                },
                {
                    "name": "dev-package",
                    "version": "3.0",
                    "groups": ["dev"],
                },
                {
                    "name": "optional-package",
                    "version": "4.0",
                    "groups": ["main"],
                    "optional": True,
                },
            ]
        )
        output = self.root / "poetry.target.lock"
        report = filter_lock_file(lock, output, self.environment)

        filtered = tomlkit.parse(output.read_text(encoding="utf-8"))
        names = {package["name"] for package in filtered["package"]}
        self.assertEqual(names, {"linux-package"})
        self.assertEqual(report["included_packages"], ["linux-package"])
        self.assertEqual(
            [item["package"] for item in report["excluded_packages"]],
            ["dev-package", "optional-package", "windows-package"],
        )

    def test_prunes_dependencies_to_retained_packages(self) -> None:
        lock = self.write_lock(
            [
                {
                    "name": "linux-package",
                    "version": "1.0",
                    "groups": ["main"],
                    "markers": "sys_platform == 'linux'",
                    "dependencies": {
                        "linux-helper": ">=1",
                        "windows-helper": ">=2",
                    },
                },
                {
                    "name": "linux-helper",
                    "version": "1.1",
                    "groups": ["main"],
                    "markers": "sys_platform == 'linux'",
                },
                {
                    "name": "windows-helper",
                    "version": "2.2",
                    "groups": ["main"],
                    "markers": "sys_platform == 'win32'",
                },
            ]
        )
        output = self.root / "poetry.target.lock"
        filter_lock_file(lock, output, self.environment)

        filtered = tomlkit.parse(output.read_text(encoding="utf-8"))
        packages = {package["name"]: package for package in filtered["package"]}
        self.assertEqual(set(packages), {"linux-package", "linux-helper"})
        self.assertEqual(
            dict(packages["linux-package"]["dependencies"]),
            {"linux-helper": ">=1"},
        )

    def test_prunes_extras_to_retained_packages(self) -> None:
        lock = self.write_lock(
            [
                {
                    "name": "linux-package",
                    "version": "1.0",
                    "groups": ["main"],
                    "markers": "sys_platform == 'linux'",
                    "extras": {
                        "full": [
                            "linux-helper>=1",
                            "windows-helper>=2",
                        ]
                    },
                },
                {
                    "name": "linux-helper",
                    "version": "1.1",
                    "groups": ["main"],
                    "markers": "sys_platform == 'linux'",
                },
                {
                    "name": "windows-helper",
                    "version": "2.2",
                    "groups": ["main"],
                    "markers": "sys_platform == 'win32'",
                },
            ]
        )
        output = self.root / "poetry.target.lock"
        filter_lock_file(lock, output, self.environment)

        filtered = tomlkit.parse(output.read_text(encoding="utf-8"))
        package = next(
            package
            for package in filtered["package"]
            if package["name"] == "linux-package"
        )
        self.assertEqual(list(package["extras"]["full"]), ["linux-helper>=1"])

    def test_include_optional_can_retain_optional_packages(self) -> None:
        lock = self.write_lock(
            [
                {
                    "name": "optional-package",
                    "version": "1.0",
                    "groups": ["main"],
                    "optional": True,
                }
            ]
        )
        output = self.root / "poetry.target.lock"
        report = filter_lock_file(
            lock,
            output,
            self.environment,
            include_optional=True,
        )
        self.assertEqual(report["included_packages"], ["optional-package"])


if __name__ == "__main__":
    unittest.main()
