"""Collection guard for the course_applications tests."""

import pytest

from django.contrib.sites.models import Site

from freedom_ls.tests.app_guards import app_not_installed, ignore_tests_unless_installed

collect_ignore_glob = ignore_tests_unless_installed("freedom_ls.course_applications")


@pytest.fixture(autouse=True)
def _terms_not_required_by_default(settings) -> None:
    """The dev settings turn consent on; tests opt in with a SiteSignupPolicy."""
    settings.REQUIRE_TERMS_ACCEPTANCE = False


@pytest.fixture
def auth(mock_site_context: Site) -> dict[str, str]:
    """Bearer headers for a key scoped to course applications.

    The imports are inside the body: the API app is optional, and importing
    its models at conftest load would take every test in this app down with it.
    """
    if app_not_installed("freedom_ls.api"):
        pytest.skip("freedom_ls.api not installed")
    from freedom_ls.api.scopes import ApiScope
    from freedom_ls.api.tests.helpers import bearer_auth_for

    return bearer_auth_for(ApiScope.COURSE_APPLICATIONS)
