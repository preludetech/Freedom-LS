from dataclasses import asdict
from unittest.mock import MagicMock, patch

import pytest

from freedom_ls.accounts.allauth_account_adapter import AccountAdapter
from freedom_ls.accounts.email_utils import get_email_theme


@pytest.mark.django_db
def test_send_mail_injects_resolved_theme_values(mock_site_context):
    """AccountAdapter.send_mail injects the resolved email theme into the context.

    The theme values are built only when an email is sent (no longer via a
    global context processor), so this verifies they reach the email context
    and match get_email_theme().
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
    ):
        mock_ctx.request = None

        def capture_ctx(template_prefix, email, ctx):
            captured.update(ctx)
            m = MagicMock()
            m.send = MagicMock()
            return m

        mock_render_mail.side_effect = capture_ctx
        adapter.send_mail("account/email/login_code", "user@example.com", {})

    theme = get_email_theme()
    for field, value in asdict(theme).items():
        assert captured[field] == value
