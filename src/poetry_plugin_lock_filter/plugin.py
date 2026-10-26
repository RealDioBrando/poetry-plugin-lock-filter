"""Poetry application plugin registration."""

from __future__ import annotations

from poetry.plugins.application_plugin import ApplicationPlugin

from poetry_plugin_lock_filter.command import FilterLockCommand


class FilterLockApplicationPlugin(ApplicationPlugin):
    @property
    def commands(self) -> list[type]:
        return [FilterLockCommand]
