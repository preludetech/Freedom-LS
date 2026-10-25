"""Shared pytest fixtures for all tests.

Re-exports all fixtures from Freedom-LS conftest to avoid duplication.
Also defines `pytest_xdist_auto_num_workers`, since a pytest hook can only live in a
`conftest.py` or a plugin.
"""

import os

import pytest

from freedom_ls.conftest import *  # noqa: F403

# freedom_ls/conftest.py registers the `playwright` override for every test under freedom_ls/,
# and nothing outside it runs Playwright. Registering the override here too would make it wrap
# itself, so its teardown ran twice per session.
del playwright  # noqa: F821


def pytest_xdist_auto_num_workers(config: pytest.Config) -> int:
    """Cap `-n auto`/`-n logical` at 4 workers, what the shared dev server can serve."""
    return min(4, os.cpu_count() or 1)
