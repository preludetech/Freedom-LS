import pytest

from django.test import RequestFactory, override_settings

from freedom_ls.site_aware_models.context_processors import site_config


@pytest.mark.django_db
def test_site_config_exposes_branding_paths_from_settings(mock_site_context):
    """site_config exposes the header logo and favicon static paths from settings."""
    request = RequestFactory().get("/")

    with override_settings(
        HEADER_LOGO_STATIC_PATH="images/logo.png",
        FAVICON_STATIC_PATH="images/favicon.ico",
    ):
        context = site_config(request)

    assert context["header_logo_static_path"] == "images/logo.png"
    assert context["favicon_static_path"] == "images/favicon.ico"


@pytest.mark.django_db
def test_site_config_branding_paths_default_to_none(mock_site_context):
    """When the branding settings are unset, the context values are None."""
    request = RequestFactory().get("/")

    with override_settings(HEADER_LOGO_STATIC_PATH=None, FAVICON_STATIC_PATH=None):
        context = site_config(request)

    assert context["header_logo_static_path"] is None
    assert context["favicon_static_path"] is None
