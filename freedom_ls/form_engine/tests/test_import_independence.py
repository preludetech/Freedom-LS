"""Guards form_engine's helper modules against depending on `models` at import time.

`form_engine.models` imports `scoring`, `signals` and `submissions`. If any of those
imported `models` back at runtime, the pair would only load in one order — the order
Django's app registry happens to use. Anything importing a helper first (as
`reports.indexes` does with `scoring`) would then die with an ImportError, and which
way round it went would depend on `INSTALLED_APPS` ordering in the installing project.

A fresh interpreter is the only way to prove this: by the time pytest runs, Django has
already imported every models module.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]

PROBE = """
import sys

import freedom_ls.form_engine.{module}

assert "freedom_ls.form_engine.models" not in sys.modules, (
    "importing form_engine.{module} pulled in form_engine.models"
)
"""


@pytest.mark.parametrize("module", ["scoring", "signals", "submissions"])
def test_helper_imports_without_the_models_module(module: str) -> None:
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", PROBE.format(module=module)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )

    assert result.returncode == 0, result.stderr
