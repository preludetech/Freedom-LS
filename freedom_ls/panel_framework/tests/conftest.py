"""Test fixtures for panel_framework - no cross-app imports.

The stub models live in ``stub_models.py`` and their constructors in ``helpers.py``.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import pytest_django.fixtures

from django.apps import apps
from django.conf import settings as django_settings
from django.contrib.contenttypes.models import ContentType
from django.core.files.storage import FileSystemStorage
from django.db import connection

# Relative, not the freedom_ls.-prefixed absolute form: this project's
# namespace-package layout (no freedom_ls/__init__.py) makes pytest import
# every module under tests/ as panel_framework.tests.*, so an absolute import
# here would load stub_panels.py under a second module name and hand this
# fixture a RecordingCapabilityConfig the test files never see -- the same
# hazard stub_panels.py's own module docstring works around for StubModel.
from .helpers import use_temp_file_storage
from .stub_models import (
    StubChild,
    StubFileModel,
    StubGrandchild,
    StubModel,
    StubProtectedChild,
)
from .stub_panels import RecordingCapabilityConfig

# A host project's conftest provides `site` and `mock_site_context`, wired
# to however that host tracks its site. With no host around the framework
# there are none, so the framework's own apply.
if (
    django_settings.SETTINGS_MODULE
    == "freedom_ls.panel_framework.tests.standalone_settings"
):
    from .standalone_fixtures import mock_site_context, site

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
    app_models["stubfilemodel"] = StubFileModel

    # With --nomigrations the test database is built from the registered models,
    # stubs included, so only the tables that are missing get created, and only
    # those are dropped at the end.
    stub_models = [
        StubModel,
        StubChild,
        StubGrandchild,
        StubProtectedChild,
        StubFileModel,
    ]
    with django_db_blocker.unblock():
        existing_tables = set(connection.introspection.table_names())
        created_models = [
            model
            for model in stub_models
            if model._meta.db_table not in existing_tables
        ]
        with connection.schema_editor() as editor:
            for model in created_models:
                editor.create_model(model)
    # A content type row made inside a test's transaction is rolled back with
    # it while ContentType's cache keeps it, so a later test that points a
    # generic foreign key at a stub would reference a row that is gone. Make
    # the rows once here, outside any transaction, like post_migrate does for
    # real models.
    with django_db_blocker.unblock():
        ContentType.objects.get_for_models(StubModel, StubChild)

    yield

    with django_db_blocker.unblock():
        ContentType.objects.filter(
            app_label="freedom_ls_panel_framework",
            model__in=["stubmodel", "stubchild"],
        ).delete()
        ContentType.objects.clear_cache()

    with django_db_blocker.unblock(), connection.schema_editor() as editor:
        for model in reversed(created_models):
            editor.delete_model(model)
    app_models.pop("stubfilemodel", None)
    app_models.pop("stubprotectedchild", None)
    app_models.pop("stubgrandchild", None)
    app_models.pop("stubmodel", None)
    app_models.pop("stubchild", None)


@pytest.fixture(autouse=True)
def _stub_file_storage(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> FileSystemStorage:
    """Keep every stub upload in the test's own directory, so no test can write
    into MEDIA_ROOT by forgetting to ask for a storage."""
    return use_temp_file_storage(monkeypatch, tmp_path)


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
_FRAMEWORK_TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"


@pytest.fixture(autouse=True)
def _use_panel_test_templates(settings: pytest_django.fixtures.SettingsWrapper) -> None:
    """Make panel_framework's test-only templates loadable, and its own
    templates win over any host's.

    `test_extra_oob_fragment.html` and the other `test_*` templates are test fixtures,
    not app templates. They live here rather than in the app's template
    directory, where the app-directories loader would resolve them in every
    project that installs FLS. Prepending this directory keeps their template
    names unchanged while confining them to the test run.

    The framework's own template directory follows, ahead of every directory
    the project configured, so a host that overrides a primitive (a
    `cotton/panel-chip.html` of its own) never reaches the framework's own
    tiers: they render the framework default.

    The copy is deliberate: mutating DIRS in place would neither trigger the
    template-engine reset nor be undone after the test.
    """
    templates = copy.deepcopy(settings.TEMPLATES)
    templates[0]["DIRS"] = [
        str(_TEST_TEMPLATES_DIR),
        str(_FRAMEWORK_TEMPLATES_DIR),
        *templates[0]["DIRS"],
    ]
    settings.TEMPLATES = templates


@pytest.fixture(autouse=True)
def _use_minimal_shell_for_reference(
    settings: pytest_django.fixtures.SettingsWrapper,
) -> None:
    """The reference page extends the framework's own shell in every test,
    whatever base the host project names."""
    settings.PANEL_REFERENCE_BASE_TEMPLATE = "panel_framework/minimal_shell.html"


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
