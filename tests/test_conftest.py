"""Tests for the root `conftest.py`'s xdist worker-count hook.

No database access: `pytest_xdist_auto_num_workers` is a pure function of the machine's
CPU count.

`freedom_ls` has no `__init__.py`, so pytest imports `freedom_ls/conftest.py` under the
same bare module name (`conftest`) as this repo's root `conftest.py`. Whichever one
collection touches last wins `sys.modules["conftest"]`, so a plain `import conftest`
here would sometimes fetch the wrong module. Loading the root file by path sidesteps
that name collision, the same way `test_settings_dev.py` loads a pristine
`config.settings_dev`.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest


def _load_root_conftest() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "_root_conftest_under_test",
        Path(__file__).resolve().parent.parent / "conftest.py",
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("cpu_count", [8, 16])
def test_worker_count_capped_at_four_on_many_cores(mocker, cpu_count: int) -> None:
    mocker.patch("os.cpu_count", return_value=cpu_count)
    root_conftest = _load_root_conftest()

    workers = root_conftest.pytest_xdist_auto_num_workers(config=None)

    assert workers == 4


def test_worker_count_matches_cpu_count_below_the_cap(mocker) -> None:
    mocker.patch("os.cpu_count", return_value=2)
    root_conftest = _load_root_conftest()

    workers = root_conftest.pytest_xdist_auto_num_workers(config=None)

    assert workers == 2


def test_worker_count_is_one_when_cpu_count_is_unknown(mocker) -> None:
    mocker.patch("os.cpu_count", return_value=None)
    root_conftest = _load_root_conftest()

    workers = root_conftest.pytest_xdist_auto_num_workers(config=None)

    assert workers == 1
