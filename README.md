# poetry-plugin-lock-filter

A Poetry 2.x plugin and standalone CLI for creating **marker-specific lock files**.

Poetry writes a universal `poetry.lock` that contains every marker branch. Installation evaluates those markers at runtime, but the lock file itself remains broad. This project post-processes a Poetry lock file and keeps only packages whose markers match a selected target environment.

## Why

Given dependencies such as:

```toml
[tool.poetry.dependencies]
linux-only = { version = "1.0", markers = "sys_platform == 'linux'" }
windows-only = { version = "2.0", markers = "sys_platform == 'win32'" }
```

Poetry 2.4.1 writes both packages to `poetry.lock`, even when only one branch is active on the current machine.

`poetry install` selects the correct packages, but tools that read `poetry.lock` directly often see both branches. This plugin produces a clean, target-specific lock file without changing the original.

## Features

- Poetry plugin command: `poetry filter-lock`
- Standalone command: `poetry-lock-filter`
- Presets for common target environments
- Repeated `--env KEY=VALUE` overrides
- Main-group filtering by default
- Optional-package exclusion by default
- Dependency pruning so retained packages only reference retained dependencies
- JSON report output
- Original `poetry.lock` is preserved by default

## Installation

Install as a Poetry plugin:

```bash
poetry self add poetry-plugin-lock-filter
```

Or install it as a normal Python package:

```bash
pip install poetry-plugin-lock-filter
```

## Poetry plugin usage

Run inside a Poetry project:

```bash
poetry filter-lock
```

This reads the project’s `poetry.lock` and writes:

```text
poetry.target.lock
```

The default target environment is:

```text
Linux
aarch64
CPython 3.11
```

## Standalone usage

```bash
poetry-lock-filter \
  --project /path/to/project \
  --output poetry.target.lock \
  --preset linux-aarch64-cp311
```

If `--project` is omitted, the command uses the current directory.

## Target presets

- `current`
- `linux-aarch64-cp311`
- `linux-x86_64-cp311`
- `windows-x86_64-cp311`

Override individual environment markers:

```bash
poetry filter-lock \
  --preset linux-aarch64-cp311 \
  --env python_version=3.11 \
  --env platform_machine=aarch64
```

Use `--preset current` to filter for the machine running the command.

## Options

```text
--output PATH            Output lock file; default poetry.target.lock
--preset NAME            Target environment preset
--env KEY=VALUE          Override a marker environment value; repeatable
--group NAME             Dependency group to retain; default main
--include-optional       Keep optional packages
--report PATH            Write a JSON filtering report
--no-check               Do not require a fresh lock file
```

The standalone command also supports:

```text
--project PATH           Poetry project directory
--lock PATH              Explicit lock file path
```

## Example report

```json
{
  "status": "success",
  "input": "poetry.lock",
  "output": "poetry.target.lock",
  "group": "main",
  "target_environment": {
    "python_version": "3.11",
    "sys_platform": "linux",
    "platform_machine": "aarch64"
  },
  "included_packages": ["linux-only"],
  "excluded_packages": [
    {
      "package": "windows-only",
      "reason": "marker",
      "marker": "sys_platform == \"win32\""
    }
  ]
}
```

## Dependency pruning

The filter also removes dependency references from retained packages when the referenced package was excluded.

For example, if `linux-only` depends on `linux-helper`, and both match the target environment, both are retained. If `linux-only` has a Windows-only dependency, that dependency edge is removed from the filtered lock.

## Compatibility

- Python 3.11 or newer
- Poetry 2.1 or newer
- Poetry lock format 2.1 or newer

## Development

```bash
python -m venv .venv
.venv/bin/python -m pip install -e .[dev]
.venv/bin/python -m unittest discover -s tests -v
```

## License

MIT


## Related projects

- [poetry-plugin-export](https://github.com/python-poetry/poetry-plugin-export) exports a Poetry lock file to requirements formats, but does not create a marker-filtered lock file.
- [poetry-lock-package](https://github.com/bneijt/poetry-lock-package) turns a lock file into a pinned package, but does not filter packages by environment markers.
- [ofiuco](https://github.com/oxidase/ofiuco) provides Bazel rules for cross-platform Poetry lock files, but is not a Poetry plugin or standalone marker filter.
