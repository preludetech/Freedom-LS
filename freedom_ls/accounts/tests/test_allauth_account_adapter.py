"""Tests for AccountAdapter."""

import email.policy
from unittest.mock import MagicMock, patch

import pytest
from allauth.core.context import request_context

from django.core import mail
from django.test import RequestFactory

from freedom_ls.accounts.allauth_account_adapter import AccountAdapter
from freedom_ls.accounts.factories import UserFactory


@pytest.mark.django_db
def test_send_notification_mail_adds_user_to_context(mock_site_context: object) -> None:
    """send_notification_mail should add `user` to the context dict before delegating."""
    user = UserFactory()
    adapter = AccountAdapter()
    context: dict[str, object] = {"some_key": "some_value"}

    # Patch the upstream allauth method (system boundary — we don't want
    # allauth resolving a real email template / sending mail).
    with patch(
        "allauth.account.adapter.DefaultAccountAdapter.send_notification_mail"
    ) as mock_super:
        adapter.send_notification_mail("account/email/test", user, context)

    forwarded_context = mock_super.call_args.args[2]
    assert forwarded_context["user"] is user
    assert forwarded_context["some_key"] == "some_value"


@pytest.mark.django_db
def test_send_notification_mail_creates_context_if_none(
    mock_site_context: object,
) -> None:
    """When no context is passed, one is created with the user populated."""
    user = UserFactory()
    adapter = AccountAdapter()

    with patch(
        "allauth.account.adapter.DefaultAccountAdapter.send_notification_mail"
    ) as mock_super:
        adapter.send_notification_mail("account/email/test", user, None)

    forwarded_context = mock_super.call_args.args[2]
    assert forwarded_context["user"] is user


def _body_parts(mime_msg: object) -> list:
    """Return the text/plain and text/html parts of a MIME message."""
    return [
        part
        for part in mime_msg.walk()
        if part.get_content_type() in ("text/plain", "text/html")
    ]


@pytest.fixture
def long_url_email(mock_site_context):
    """Send an allauth password-reset email containing a long URL.

    Returns ``(long_url, body_parts)`` so individual tests can assert on
    one property of the rendered MIME parts at a time.
    """
    user = UserFactory()
    adapter = AccountAdapter()

    long_url = "http://testsite/account/password/reset/key/" + "a" * 80 + "/"
    context = {"password_reset_url": long_url, "user": user}

    request = RequestFactory().get("/")
    with request_context(request):
        adapter.send_mail("account/email/password_reset_key", user.email, context)

    assert len(mail.outbox) == 1
    return long_url, _body_parts(mail.outbox[0].message())


@pytest.mark.django_db
def test_send_mail_emits_at_least_one_body_part(long_url_email) -> None:
    _, parts = long_url_email
    assert parts, "expected at least one text/plain or text/html body part"


@pytest.mark.django_db
@pytest.mark.parametrize("soft_break", ["=\n", "=\r\n"])
def test_send_mail_avoids_quoted_printable_line_wrapping(
    long_url_email, soft_break: str
) -> None:
    """Quoted-printable wraps lines >76 chars with =\\n, which corrupts URLs."""
    _, parts = long_url_email
    payloads = [part.get_payload() for part in parts]
    assert all(soft_break not in payload for payload in payloads)


@pytest.mark.django_db
def test_send_mail_preserves_long_url_in_body(long_url_email) -> None:
    long_url, parts = long_url_email
    payloads = [part.get_payload() for part in parts]
    assert all(long_url in payload for payload in payloads)


@pytest.mark.django_db
def test_send_mail_uses_8bit_transfer_encoding(long_url_email) -> None:
    _, parts = long_url_email
    encodings = [part["Content-Transfer-Encoding"] for part in parts]
    assert all(encoding == "8bit" for encoding in encodings)


@pytest.mark.django_db
def test_send_mail_logo_url_uses_request_absolute_uri(
    mock_site_context, settings
) -> None:
    """With a request in context, the logo URL is built from the request host.

    Regression for the broken-logo bug: the logo was built from the Site domain
    + ACCOUNT_DEFAULT_HTTP_PROTOCOL (e.g. https://127.0.0.1/static/...), which is
    unreachable in dev, while the action links use the request-based absolute URI.
    The logo must use the same request-based builder so it resolves.
    """
    from django.templatetags.static import static

    settings.EMAIL_LOGO_STATIC_PATH = "images/test_logo.png"
    settings.HEADER_LOGO_STATIC_PATH = None

    captured: dict = {}
    adapter = AccountAdapter()

    # RequestFactory's default host is "testserver" (allowed in tests). The
    # point is that the logo uses the request host, not the bare Site domain.
    request = RequestFactory().get("/")

    def capture_ctx(template_prefix, email, ctx):
        captured.update(ctx)
        m = MagicMock()
        m.send = MagicMock()
        return m

    with (
        patch.object(adapter, "render_mail", side_effect=capture_ctx),
        patch(
            "freedom_ls.accounts.allauth_account_adapter.get_current_site",
            return_value=mock_site_context,
        ),
        request_context(request),
    ):
        adapter.send_mail("account/email/login_code", "user@example.com", {})

    logo_url = captured["email_logo_url"]
    assert logo_url == request.build_absolute_uri(static("images/test_logo.png"))
    assert logo_url == "http://testserver" + static("images/test_logo.png")


@pytest.mark.django_db
def test_send_mail_logo_url_uses_absolute_static_url_verbatim(
    mock_site_context, settings
) -> None:
    """When STATIC_URL is already absolute (a CDN), the logo URL is used as-is.

    The Site-domain fallback must not prefix an already-qualified CDN URL, which
    would produce a malformed https://domain/https://cdn.../logo.png.
    """
    settings.EMAIL_LOGO_STATIC_PATH = "images/test_logo.png"
    settings.HEADER_LOGO_STATIC_PATH = None
    settings.STATIC_URL = "https://cdn.example.com/static/"

    captured: dict = {}
    adapter = AccountAdapter(request=None)

    def capture_ctx(template_prefix, email, ctx):
        captured.update(ctx)
        m = MagicMock()
        m.send = MagicMock()
        return m

    with (
        patch.object(adapter, "render_mail", side_effect=capture_ctx),
        patch(
            "freedom_ls.accounts.allauth_account_adapter.allauth_context"
        ) as mock_ctx,
        patch(
            "freedom_ls.accounts.allauth_account_adapter.get_current_site",
            return_value=mock_site_context,
        ),
    ):
        mock_ctx.request = None
        adapter.send_mail("account/email/login_code", "user@example.com", {})

    assert (
        captured["email_logo_url"]
        == "https://cdn.example.com/static/images/test_logo.png"
    )


@pytest.mark.django_db
def test_send_mail_message_accepts_policy_kwarg(mock_site_context) -> None:
    """Django's SMTP backend calls message(policy=...); the 8bit patch must forward it."""
    user = UserFactory()
    adapter = AccountAdapter()
    context = {
        "password_reset_url": "http://testsite/account/password/reset/key/x/",  # pragma: allowlist secret
        "user": user,
    }

    request = RequestFactory().get("/")
    with request_context(request):
        adapter.send_mail("account/email/password_reset_key", user.email, context)

    sent = mail.outbox[0]
    mime = sent.message(policy=email.policy.SMTP)
    parts = _body_parts(mime)
    assert all(part["Content-Transfer-Encoding"] == "8bit" for part in parts)
