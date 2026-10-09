from __future__ import annotations

import os

import pytest

from freedom_ls.deployment.tests.helpers import PRODUCTION_ENV, set_env


@pytest.fixture(autouse=True)
def _clear_aws_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear every AWS_* variable first, so a developer's real credentials
    exported for an unrelated project never change these results."""
    for name in [name for name in os.environ if name.startswith("AWS_")]:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def production_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Apply PRODUCTION_ENV, the intended production storage configuration."""
    set_env(monkeypatch, PRODUCTION_ENV)
