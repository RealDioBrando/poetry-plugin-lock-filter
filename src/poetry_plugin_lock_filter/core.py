"""Core marker-specific Poetry lock filtering logic."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import tomlkit
from packaging.markers import Marker, default_environment
from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name

PRESETS: dict[str, dict[str, str] | None] = {
    "current": None,
    "linux-aarch64-cp311": {
        "implementation_name": "cpython",
        "implementation_version": "3.11.0",
        "os_name": "posix",
        "platform_machine": "aarch64",
        "platform_python_implementation": "CPython",
        "platform_release": "",
        "platform_system": "Linux",
        "platform_version": "",
        "python_full_version": "3.11.0",
        "python_version": "3.11",
        "sys_platform": "linux",
    },
    "linux-x86_64-cp311": {
        "implementation_name": "cpython",
        "implementation_version": "3.11.0",
        "os_name": "posix",
        "platform_machine": "x86_64",
        "platform_python_implementation": "CPython",
        "platform_release": "",
        "platform_system": "Linux",
        "platform_version": "",
        "python_full_version": "3.11.0",
        "python_version": "3.11",
        "sys_platform": "linux",
    },
    "windows-x86_64-cp311": {
        "implementation_name": "cpython",
        "implementation_version": "3.11.0",
        "os_name": "nt",
        "platform_machine": "AMD64",
        "platform_python_implementation": "CPython",
        "platform_release": "",
        "platform_system": "Windows",
        "platform_version": "",
        "python_full_version": "3.11.0",
        "python_version": "3.11",
        "sys_platform": "win32",
    },
}


class LockFilterError(RuntimeError):
    """A user-facing lock filtering failure."""


def build_environment(preset: str, overrides: Mapping[str, str]) -> dict[str, str]:
    if preset == "current":
        environment = dict(default_environment())
    else:
        preset_environment = PRESETS.get(preset)
        if preset_environment is None:
            raise LockFilterError(f"Unknown environment preset: {preset}")
        environment = dict(preset_environment)

    environment.update(dict(overrides))
    return environment


def marker_applies(marker: Any, environment: Mapping[str, str], group: str) -> bool:
    if marker in (None, "", "*"):
        return True
    if isinstance(marker, str):
        return Marker(marker).evaluate(dict(environment))
    if isinstance(marker, Mapping):
        return marker_applies(marker.get(group, "*"), environment, group)
    raise LockFilterError(f"Unsupported Poetry lock marker value: {marker!r}")


def _package_name(package: Mapping[str, Any]) -> str:
    return canonicalize_name(str(package.get("name", "")))


def _requirement_name(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return canonicalize_name(Requirement(value).name)
    except InvalidRequirement:
        return None


def _prune_dependencies(
    package: Mapping[str, Any], included: set[str]
) -> dict[str, Any]:
    """Remove dependency references from a retained package.

    Poetry lock package entries list dependencies without marker information.
    When a referenced package is excluded by this filter, retaining the edge
    would leave an inconsistent lock file.
    """
    result = dict(package)
    dependencies = result.get("dependencies")
    if isinstance(dependencies, Mapping):
        kept_dependencies = {
            key: value
            for key, value in dependencies.items()
            if canonicalize_name(str(key)) in included
        }
        if kept_dependencies:
            result["dependencies"] = kept_dependencies
        else:
            result.pop("dependencies", None)
    return result


def _prune_extras(package: Mapping[str, Any], included: set[str]) -> dict[str, Any]:
    """Remove extra requirements that reference excluded packages."""
    result = dict(package)
    extras = result.get("extras")
    if isinstance(extras, Mapping):
        kept_extras: dict[str, Any] = {}
        for extra, requirements in extras.items():
            if isinstance(requirements, list):
                kept = [
                    requirement
                    for requirement in requirements
                    if (name := _requirement_name(requirement)) is None
                    or name in included
                ]
                if kept:
                    kept_extras[str(extra)] = kept
            else:
                kept_extras[str(extra)] = requirements
        if kept_extras:
            result["extras"] = kept_extras
        else:
            result.pop("extras", None)
    return result


def _new_package_array() -> Any:
    # tomlkit does not expose a direct AoT constructor in its public API.
    # Parsing a one-entry AoT and clearing it gives a reusable container.
    container = tomlkit.parse("[[package]]\n")["package"]
    container.clear()
    return container


def filter_lock_file(
    lock_file: Path,
    output_file: Path,
    environment: Mapping[str, str],
    *,
    group: str = "main",
    include_optional: bool = False,
) -> dict[str, Any]:
    if not lock_file.is_file():
        raise LockFilterError(f"Poetry lock file does not exist: {lock_file}")

    document = tomlkit.parse(lock_file.read_text(encoding="utf-8"))
    packages = document.get("package", [])

    retained: list[dict[str, Any]] = []
    included: set[str] = set()
    excluded: list[dict[str, Any]] = []

    for package in packages:
        name = _package_name(package)
        groups = package.get("groups", ["main"])
        if group not in groups:
            excluded.append(
                {"package": name, "reason": "group", "groups": list(groups)}
            )
            continue

        if package.get("optional", False) and not include_optional:
            excluded.append({"package": name, "reason": "optional"})
            continue

        marker = package.get("markers", "*")
        if not marker_applies(marker, environment, group):
            excluded.append(
                {"package": name, "reason": "marker", "marker": str(marker)}
            )
            continue

        retained.append(dict(package))
        included.add(name)

    package_array = _new_package_array()
    for package in retained:
        package = _prune_dependencies(package, included)
        package = _prune_extras(package, included)
        package_array.append(package)

    output_document = tomlkit.document()
    output_document["package"] = package_array
    for key, value in document.items():
        if key != "package":
            output_document[key] = value

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(tomlkit.dumps(output_document), encoding="utf-8")

    return {
        "status": "success",
        "input": str(lock_file.resolve()),
        "output": str(output_file.resolve()),
        "group": group,
        "include_optional": include_optional,
        "target_environment": dict(environment),
        "included_packages": sorted(included),
        "excluded_packages": sorted(excluded, key=lambda item: item["package"]),
        "included_count": len(included),
        "excluded_count": len(excluded),
    }


def write_report(path: Path, report: Mapping[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return path
