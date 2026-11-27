"""The icons app keeps its own copies of a few freedom_ls.base helpers, because
it must run without FLS. Each copy must stay identical to its original, so a fix
to one reaches both.
"""

from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path
from types import ModuleType

import pytest

from freedom_ls.base import app_settings as base_app_settings


def _load_module_from_path(name: str, path: Path) -> ModuleType:
    """Import a file by path, for a module the icons app keeps out of its public names."""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # inspect.getsource finds a class's file through sys.modules, so register first.
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _app_module_path(package: str, module: str) -> Path:
    """The file of `package.module`, found without importing it, so this app gains no
    dependency the import contracts forbid."""
    spec = importlib.util.find_spec(package)
    assert spec is not None
    assert spec.submodule_search_locations is not None
    return Path(spec.submodule_search_locations[0]) / f"{module}.py"


icons_app_settings = _load_module_from_path(
    "icons_app_settings", _app_module_path("freedom_ls.icons", "app_settings")
)

SAME_SOURCE = [
    (base_app_settings.Setting, icons_app_settings.Setting),
    (base_app_settings.AppSettings, icons_app_settings.AppSettings),
    (base_app_settings.project_value, icons_app_settings.project_value),
]


@pytest.mark.parametrize(
    ("original", "copy"),
    SAME_SOURCE,
    ids=[
        f"{copy.__module__}.{original.__qualname__}" for original, copy in SAME_SOURCE
    ],
)
def test_a_copied_helper_has_its_originals_source(
    original: object, copy: object
) -> None:
    assert inspect.getsource(copy) == inspect.getsource(original), (
        f"{inspect.getsourcefile(copy)} and {inspect.getsourcefile(original)} "
        "have drifted: change both."
    )
