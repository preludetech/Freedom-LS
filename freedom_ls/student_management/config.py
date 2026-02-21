"""
App-level configuration for student_management.

Provides a `config` object that resolves settings by checking Django's
``settings`` first, then falling back to the defaults defined here.

Usage::

    from freedom_ls.student_management.config import config

    if config.DEADLINES_ACTIVE:
        # show deadline UI
"""

from django.conf import settings


defaults: dict[str, object] = {
    "DEADLINES_ACTIVE": True,
}


class Config:
    """Layered config: Django settings override app defaults."""

    def __init__(self, defaults: dict[str, object]) -> None:
        self._defaults = defaults

    def __getattr__(self, name: str) -> object:
        if hasattr(settings, name):
            return getattr(settings, name)
        try:
            return self._defaults[name]
        except KeyError:
            raise AttributeError(f"Config has no setting '{name}'")


config = Config(defaults)

