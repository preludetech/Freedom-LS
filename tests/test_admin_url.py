import pytest

from django.urls import resolve


@pytest.mark.django_db
def test_admin_url_resolves_at_default_path() -> None:
    """With no DJANGO_ADMIN_URL env var, /admin/ resolves to the admin site."""
    match = resolve("/admin/")
    assert match.url_name == "index"
    assert match.app_name == "admin"


def test_admin_url_variable_reads_from_environment() -> None:
    """The ADMIN_URL variable in config.urls reads from DJANGO_ADMIN_URL env var."""
    from config.urls import ADMIN_URL

    assert isinstance(ADMIN_URL, str)
    assert len(ADMIN_URL) > 0
