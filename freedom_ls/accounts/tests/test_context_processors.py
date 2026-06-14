import pytest

from django.test import RequestFactory

from freedom_ls.accounts.context_processors import email_settings
from freedom_ls.accounts.email_utils import get_email_theme


@pytest.mark.django_db
def test_email_settings_values_match_resolved_theme(mock_site_context):
    """Context processor values mirror the resolved email theme."""
    request = RequestFactory().get("/")
    context = email_settings(request)
    theme = get_email_theme()

    assert context["email_color_primary"] == theme.color_primary
    assert context["email_color_foreground"] == theme.color_foreground
    assert context["email_color_muted"] == theme.color_muted
    assert context["email_color_surface"] == theme.color_surface
    assert context["email_color_surface_2"] == theme.color_surface_2
    assert context["email_color_on_primary"] == theme.color_on_primary
    assert context["email_color_border"] == theme.color_border
    assert context["email_color_header"] == theme.color_header
    assert context["email_color_on_header"] == theme.color_on_header
    assert context["email_font_family"] == theme.font_family
    assert context["email_button_radius"] == theme.button_radius
