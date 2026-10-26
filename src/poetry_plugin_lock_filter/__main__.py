"""Allow `python -m poetry_plugin_lock_filter`."""

from poetry_plugin_lock_filter.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
