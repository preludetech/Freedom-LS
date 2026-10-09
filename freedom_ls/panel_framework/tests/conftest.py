"""Test fixtures for panel_framework - no cross-app imports.

The stub models live in ``stub_models.py`` and their constructors in ``helpers.py``.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import pytest_django.fixtures

from django.apps import apps
from django.db import connection

# Relative, not the freedom_ls.-prefixed absolute form: this project's
# namespace-package layout (no freedom_ls/__init__.py) makes pytest import
# every module under tests/ as panel_framework.tests.*, so an absolute import
# here would load stub_panels.py under a second module name and hand this
# fixture a RecordingCapabilityConfig the test files never see -- the same
# hazard stub_panels.py's own module docstring works around for StubModel.
from .stub_models import StubChild, StubGrandchild, StubModel, StubProtectedChild
from .stub_panels import RecordingCapabilityConfig

# ---------------------------------------------------------------------------
# Session-scoped table creation + permission setup
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True, scope="session")
def _panel_test_tables(django_db_setup, django_db_blocker):
    """Create stub tables once per test session.

    The unblock covers only the schema work on either side of the yield. Holding
    it open across the yield would leave the database unblocked for every later
    test in the run, so an unmarked test could write rows outside a transaction
    and leak them into unrelated tests.
    """
    # Register models in the app registry so Django's Collector can find them
    app_models = apps.all_models.get("freedom_ls_panel_framework", {})
    app_models["stubmodel"] = StubModel
    app_models["stubchild"] = StubChild
    app_models["stubgrandchild"] = StubGrandchild
    app_models["stubprotectedchild"] = StubProtectedChild

    with django_db_blocker.unblock(), connection.schema_editor() as editor:
        editor.create_model(StubModel)
        editor.create_model(StubChild)
        editor.create_model(StubGrandchild)
        editor.create_model(StubProtectedChild)

    yield

    with django_db_blocker.unblock(), connection.schema_editor() as editor:
        editor.delete_model(StubProtectedChild)
        editor.delete_model(StubGrandchild)
        editor.delete_model(StubChild)
        editor.delete_model(StubModel)
    app_models.pop("stubprotectedchild", None)
    app_models.pop("stubgrandchild", None)
    app_models.pop("stubmodel", None)
    app_models.pop("stubchild", None)


@pytest.fixture(autouse=True)
def _reset_recording_capability_config():
    """Every test gets a clean recording stub config: the default canned
    answer, no recorded scope and an empty call log."""
    RecordingCapabilityConfig.reset()
    yield
    RecordingCapabilityConfig.reset()


# ---------------------------------------------------------------------------
# Fixture: use panel_framework's own test templates
# ---------------------------------------------------------------------------

_TEST_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


@pytest.fixture(autouse=True)
def _use_panel_test_templates(settings: pytest_django.fixtures.SettingsWrapper) -> None:
    """Make panel_framework's test-only templates loadable.

    `test_interface.html` and `test_extra_oob_fragment.html` are test fixtures,
    not app templates. They live here rather than in the app's template
    directory, where the app-directories loader would resolve them in every
    project that installs FLS. Prepending this directory keeps their template
    names unchanged while confining them to the test run.

    The copy is deliberate: mutating DIRS in place would neither trigger the
    template-engine reset nor be undone after the test.
    """
    templates = copy.deepcopy(settings.TEMPLATES)
    templates[0]["DIRS"] = [str(_TEST_TEMPLATES_DIR), *templates[0]["DIRS"]]
    settings.TEMPLATES = templates


# ---------------------------------------------------------------------------
# Fixture: use panel_framework's own test URLs
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _use_panel_test_urls(settings: pytest_django.fixtures.SettingsWrapper) -> None:
    """Point Django URL resolution at panel_framework's own test URLs.

    Applied autouse so every test in panel_framework/tests/ uses the isolated
    test URL config. The panel_framework app must not depend on any consumer
    app's URLs, so tests in this directory must only reverse URLs that live in
    `root_urls.py`.
    """
    settings.ROOT_URLCONF = "freedom_ls.panel_framework.tests.root_urls"
