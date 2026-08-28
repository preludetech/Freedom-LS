"""Guards the WSGI and ASGI entry points against defaulting DJANGO_SETTINGS_MODULE.

FLS ships `settings_base`, `settings_dev` and `settings_prod` and no canonical
`config.settings`, so an entry point that guesses a settings module names one that does
not exist. Nothing inside FLS imports `config.wsgi` or `config.asgi` -- gunicorn does, in
a downstream deployment -- so without these tests neither file is exercised at all.

A fresh interpreter is the only way to prove the second pair: by the time pytest runs,
`DJANGO_SETTINGS_MODULE` is already set and settings cannot be unconfigured.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from config.asgi import application as asgi_application
from config.wsgi import application as wsgi_application

REPO_ROOT = Path(__file__).resolve().parents[1]

ENTRYPOINT_MODULES = ["config.wsgi", "config.asgi"]


def test_wsgi_entrypoint_yields_a_callable_application() -> None:
    assert callable(wsgi_application)


def test_asgi_entrypoint_yields_a_callable_application() -> None:
    assert callable(asgi_application)


@pytest.mark.parametrize("module", ENTRYPOINT_MODULES)
def test_entrypoint_without_settings_module_fails_naming_the_env_var(
    module: str,
) -> None:
    # Arrange
    stripped_env = {
        key: value
        for key, value in os.environ.items()
        if key != "DJANGO_SETTINGS_MODULE"
    }

    # Act
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", f"import {module}"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=stripped_env,
        check=False,
    )

    # Assert
    assert result.returncode != 0
    assert "DJANGO_SETTINGS_MODULE" in result.stderr
