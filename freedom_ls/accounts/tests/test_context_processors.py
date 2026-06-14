from dataclasses import asdict
from unittest.mock import MagicMock, patch

import pytest

from freedom_ls.accounts.allauth_account_adapter import AccountAdapter
from freedom_ls.accounts.email_utils import EmailTheme

# A controlled theme with sentinel values, so the test verifies the wiring
# (send_mail forwards every theme field into the email context) against an
# independent oracle rather than comparing get_email_theme() to itself.
_SENTINEL_THEME = EmailTheme(
    color_primary="#abc123",
    color_on_primary="#ffffff",
    color_foreground="#111111",
    color_muted="#666666",
    color_surface="#fefefe",
    color_surface_2="#eeeeee",
    color_border="#cccccc",
    color_header="#abc124",
    color_on_header="#222222",
    font_family='"Helvetica Neue", Arial, sans-serif',
    button_radius="0.375rem",
)


@pytest.mark.django_db
def test_send_mail_injects_resolved_theme_values(mock_site_context):
    """AccountAdapter.send_mail injects every email theme field into the context.

    The theme values are built only when an email is sent (no longer via a
    global context processor), so this verifies they reach the email context.
    """
    adapter = AccountAdapter(request=None)
    captured: dict = {}

    with (
        patch.object(adapter, "render_mail") as mock_render_mail,
        patch(
            "freedom_ls.accounts.allauth_account_adapter.allauth_context"
        ) as mock_ctx,
        patch(
            "freedom_ls.accounts.allauth_account_adapter.get_current_site",
            return_value=mock_site_context,
        ),
        patch(
            "freedom_ls.accounts.allauth_account_adapter.get_email_theme",
            return_value=_SENTINEL_THEME,
        ),
    ):
        mock_ctx.request = None

        def capture_ctx(template_prefix, email, ctx):
            captured.update(ctx)
            m = MagicMock()
            m.send = MagicMock()
            return m

        mock_render_mail.side_effect = capture_ctx
        adapter.send_mail("account/email/login_code", "user@example.com", {})

    for field, value in asdict(_SENTINEL_THEME).items():
        assert captured[field] == value
