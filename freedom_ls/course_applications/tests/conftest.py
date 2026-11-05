"""Collection guard for the course_applications tests."""

import pytest

from freedom_ls.api.factories import ApiKeyFactory
from freedom_ls.api.scopes import ApiScope
from freedom_ls.tests.app_guards import ignore_tests_unless_installed

collect_ignore_glob = ignore_tests_unless_installed("freedom_ls.course_applications")


@pytest.fixture(autouse=True)
def _terms_not_required_by_default(settings) -> None:
    """The dev settings turn consent on; tests opt in with a SiteSignupPolicy."""
    settings.REQUIRE_TERMS_ACCEPTANCE = False


@pytest.fixture
def api_key(mock_site_context):
    return ApiKeyFactory(scopes=[ApiScope.COURSE_APPLICATIONS])


@pytest.fixture
def auth(api_key) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key.issued_key}"}
