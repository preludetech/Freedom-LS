"""Collection guard for the course_applications tests."""

import pytest

from freedom_ls.tests.app_guards import app_not_installed

collect_ignore_glob: list[str] = []
if app_not_installed("freedom_ls.course_applications"):
    collect_ignore_glob = ["test_*.py"]


@pytest.fixture(autouse=True)
def _terms_not_required_by_default(settings) -> None:
    """The dev settings turn consent on; tests opt in with a SiteSignupPolicy."""
    settings.REQUIRE_TERMS_ACCEPTANCE = False
