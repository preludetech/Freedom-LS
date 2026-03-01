import pytest

from django.test import RequestFactory

from freedom_ls.accounts.context_processors import email_settings


@pytest.mark.django_db
def test_email_settings_context_processor(mock_site_context):
    """Test that email_settings returns all expected email template settings."""
    request = RequestFactory().get("/")
    context = email_settings(request)

    assert "email_color_primary" in context
    assert "email_color_foreground" in context
    assert "email_color_muted" in context
    assert "email_font_family" in context
    assert "email_logo_static_path" in context


@pytest.mark.django_db
def test_email_settings_values_match_django_settings(mock_site_context, settings):
    """Test that context processor values match Django settings."""
    request = RequestFactory().get("/")
    context = email_settings(request)

    assert context["email_color_primary"] == settings.EMAIL_COLOR_PRIMARY
    assert context["email_color_foreground"] == settings.EMAIL_COLOR_FOREGROUND
    assert context["email_color_muted"] == settings.EMAIL_COLOR_MUTED
    assert context["email_font_family"] == settings.EMAIL_FONT_FAMILY
    assert context["email_logo_static_path"] == settings.EMAIL_LOGO_STATIC_PATH
