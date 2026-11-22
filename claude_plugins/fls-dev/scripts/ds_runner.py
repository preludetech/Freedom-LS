"""Loads the generic test runner, `run_tests.py`, into the FLS scripts that read its run files."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

RUN_TESTS_PATH = (
    Path(__file__).resolve().parents[2] / "django-stack" / "scripts" / "run_tests.py"
)


def load_run_tests() -> ModuleType:
    """The `run_tests.py` module, imported by path.

    The runner lives in another plugin's directory, which is not a package on `sys.path`.
    """
    spec = importlib.util.spec_from_file_location("ds_run_tests", RUN_TESTS_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {RUN_TESTS_PATH}")
    module = importlib.util.module_from_spec(spec)
    # The runner's dataclasses look their module up in `sys.modules` while it executes.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
