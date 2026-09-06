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


@pytest.mark.django_db
def test_site_config_header_title_override(mock_site_context):
    """HEADER_TITLE overrides the header title and its inline style is exposed."""
    request = RequestFactory().get("/")

    with override_settings(
        HEADER_TITLE="FirstClass",
        HEADER_TITLE_STYLE="font-style: italic;",
    ):
        context = site_config(request)

    assert context["header_title"] == "FirstClass"
    assert context["header_title_style"] == "font-style: italic;"


@pytest.mark.django_db
def test_site_config_header_title_falls_back_to_site_name(mock_site_context):
    """Without HEADER_TITLE, header_title falls back to the site name."""
    request = RequestFactory().get("/")

    with override_settings(HEADER_TITLE=None, HEADER_TITLE_STYLE=None):
        context = site_config(request)

    assert context["header_title"] == context["site_title"] == "TestSite"
    assert context["header_title_style"] is None


@pytest.mark.django_db
@override_settings(
    ALLOWED_HOSTS=["testserver"], FORCE_SITE_NAME=None, HEADER_TITLE=None
)
def test_site_config_degrades_for_a_rejected_host():
    """A host outside ALLOWED_HOSTS yields blank branding rather than raising.

    Django's 400 handler renders with a full RequestContext, so this processor
    runs for a request whose Host header was already rejected. Raising here
    would turn that 400 into a 500.
    """
    request = RequestFactory().get("/", HTTP_HOST="not-an-allowed-host.example.com")

    context = site_config(request)

    assert context["site_name"] == ""
    assert context["header_title"] == ""
