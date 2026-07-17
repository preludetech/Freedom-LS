"""Opt-in FLS conformance suite. Downstreams import from here.

    from freedom_ls.contrib.conformance import *          # simple
    # or, collision-safe (recommended):
    from freedom_ls.contrib import conformance
    test_fls_namespace_reverses = conformance.test_fls_namespace_reverses

Prune an internal-tier route you have customised while keeping its app:
    conformance.drop("student_interface:courses")
"""

from __future__ import annotations

from ._registry import drop
from .test_migrations import test_migration_state_consistent
from .test_settings import test_configured_backend_instantiates
from .test_theme import test_active_icon_set_resolves, test_active_theme_resolves
from .test_urls import test_fls_namespace_reverses, test_reference_url_reverses

__all__ = [
    "drop",
    "test_active_icon_set_resolves",
    "test_active_theme_resolves",
    "test_configured_backend_instantiates",
    "test_fls_namespace_reverses",
    "test_migration_state_consistent",
    "test_reference_url_reverses",
]
