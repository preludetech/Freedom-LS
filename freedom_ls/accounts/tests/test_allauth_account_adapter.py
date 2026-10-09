"""Tests for AccountAdapter."""

from __future__ import annotations

import email.policy
from unittest.mock import MagicMock, patch

import pytest
from allauth.core.context import request_context

from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.sites.models import Site
from django.core import mail
from django.http import HttpRequest, HttpResponse
from django.test import RequestFactory, override_settings

from freedom_ls.accounts.allauth_account_adapter import AccountAdapter
from freedom_ls.accounts.factories import (
    SiteFactory,
    SiteSignupPolicyFactory,
    UserFactory,
)
from freedom_ls.accounts.models import SiteSignupPolicy
from freedom_ls.site_aware_models.models import (
    _CACHED_SITE_ATTR,
    SiteResolutionError,
    _thread_locals,
)


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

    Sent with no request, so FORCE_SITE_NAME names the tenant; it is the only
    thing that can without one.
    """
    settings.EMAIL_LOGO_STATIC_PATH = "images/test_logo.png"
    settings.HEADER_LOGO_STATIC_PATH = None
    settings.STATIC_URL = "https://cdn.example.com/static/"
    settings.FORCE_SITE_NAME = mock_site_context.name

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
    ):
        mock_ctx.request = None
        adapter.send_mail("account/email/login_code", "user@example.com", {})

    assert (
        captured["email_logo_url"]
        == "https://cdn.example.com/static/images/test_logo.png"
    )


@pytest.mark.django_db
def test_send_mail_logo_url_is_none_when_static_lookup_fails(
    mock_site_context, settings
) -> None:
    """A missing/uncollected logo asset must degrade to None, not break sending.

    Under ManifestStaticFilesStorage (used in production), static() raises
    ValueError when the asset is absent from the manifest. The branded logo is a
    best-effort enhancement, so a lookup failure must fall back to the text label
    rather than abort the whole transactional email.

    Sent with no request, so FORCE_SITE_NAME names the tenant; it is the only
    thing that can without one.
    """
    settings.EMAIL_LOGO_STATIC_PATH = "images/missing_logo.png"
    settings.HEADER_LOGO_STATIC_PATH = None
    settings.FORCE_SITE_NAME = mock_site_context.name

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
            "freedom_ls.accounts.allauth_account_adapter.static",
            side_effect=ValueError("Missing staticfiles manifest entry"),
        ),
    ):
        mock_ctx.request = None
        # Must not raise.
        adapter.send_mail("account/email/login_code", "user@example.com", {})

    assert captured["email_logo_url"] is None


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


@pytest.mark.django_db
class TestFormatEmailSubject:
    """The subject prefix must name the tenant the way the rest of FLS does.

    allauth's default prefixes with the raw ``Site.name`` resolved by HTTP host.
    That disagrees with the email body, which names the tenant HEADER_TITLE-first,
    and it ignores FORCE_SITE_NAME. On an installation whose Site row was created
    without a display name, ``Site.name`` is the bare domain, so the subject read
    "[learn.example.com] ..." while the body read the product's name.
    """

    SUBJECT = "Confirm your email address"

    @staticmethod
    def _format(subject: str) -> str:
        """Format a subject with no request in context (mail sent off-request)."""
        adapter = AccountAdapter(request=None)
        with patch(
            "freedom_ls.accounts.allauth_account_adapter.allauth_context"
        ) as mock_ctx:
            mock_ctx.request = None
            return adapter.format_email_subject(subject)

    def test_prefix_uses_header_title_when_set(
        self, mock_site_context: Site, settings
    ) -> None:
        settings.HEADER_TITLE = "MyProduct"

        assert self._format(self.SUBJECT) == f"[MyProduct] {self.SUBJECT}"

    def test_header_title_answers_without_resolving_a_site(
        self, settings, django_assert_num_queries
    ) -> None:
        """No mock_site_context here, deliberately.

        Mail is not always sent from a request, and with nothing pinned there is
        no tenant to resolve -- the resolver raises. A name HEADER_TITLE already
        answers must not need one, or cost a query.
        """
        settings.HEADER_TITLE = "MyProduct"

        with django_assert_num_queries(0):
            assert self._format(self.SUBJECT) == f"[MyProduct] {self.SUBJECT}"

    def test_prefix_falls_back_to_site_name_without_header_title(
        self, mock_site_context: Site, settings
    ) -> None:
        """With no HEADER_TITLE the name comes from the Site row itself.

        Pinned, because the subject is formatted off-request and FORCE_SITE_NAME
        is the only thing that names a tenant without one.
        """
        settings.HEADER_TITLE = ""
        settings.FORCE_SITE_NAME = mock_site_context.name

        assert self._format(self.SUBJECT) == f"[TestSite] {self.SUBJECT}"

    def test_prefix_honours_forced_site_name(
        self, mock_site_context: Site, settings
    ) -> None:
        """A single-tenant install pinned with FORCE_SITE_NAME gets that site."""
        settings.HEADER_TITLE = ""
        Site.objects.create(domain="pinned.example.test", name="PinnedSite")
        settings.FORCE_SITE_NAME = "PinnedSite"

        assert self._format(self.SUBJECT) == f"[PinnedSite] {self.SUBJECT}"

    def test_nothing_pinned_refuses_rather_than_naming_a_tenant(self, settings) -> None:
        """No request, and nothing pinned to stand in for one.

        Deliberately no ``mock_site_context`` -- that fixture patches the site
        resolution this exercises. Holding one Site row is not an answer: the
        caller still cannot say which tenant it is, and a subject line carries
        that name to the recipient. Refusing beats sending under the wrong one.
        """
        settings.HEADER_TITLE = ""
        only_site = Site.objects.get()
        only_site.name = "OnlyTenant"
        only_site.save(update_fields=["name"])

        with pytest.raises(SiteResolutionError):
            self._format(self.SUBJECT)

    def test_explicit_subject_prefix_setting_still_wins(
        self, mock_site_context: Site, settings
    ) -> None:
        """allauth's own escape hatch keeps working."""
        settings.HEADER_TITLE = "MyProduct"
        settings.ACCOUNT_EMAIL_SUBJECT_PREFIX = "[Fixed] "

        assert self._format(self.SUBJECT) == f"[Fixed] {self.SUBJECT}"

    def test_sent_email_carries_the_display_name_in_its_subject(
        self, mock_site_context: Site, settings
    ) -> None:
        """End to end through render_mail, not just the prefix helper."""
        settings.HEADER_TITLE = "MyProduct"
        user = UserFactory()
        adapter = AccountAdapter()
        context = {
            "password_reset_url": "http://testsite/account/password/reset/key/x/",  # pragma: allowlist secret
            "user": user,
        }

        with request_context(RequestFactory().get("/")):
            adapter.send_mail("account/email/password_reset_key", user.email, context)

        assert mail.outbox[0].subject == "[MyProduct] Reset your password"


@pytest.mark.django_db
def test_falls_back_to_global_setting_when_no_policy(mock_site_context, settings):
    """If no SiteSignupPolicy exists for the current site, use settings.ALLOW_SIGN_UPS."""
    settings.ALLOW_SIGN_UPS = True

    request = RequestFactory().get("/")
    assert AccountAdapter().is_open_for_signup(request) is True


@pytest.mark.django_db
def test_policy_overrides_global_setting(mock_site_context, settings, site):
    """Per-site SiteSignupPolicy should override settings.ALLOW_SIGN_UPS."""
    settings.ALLOW_SIGN_UPS = False  # global signups are not allowed

    SiteSignupPolicy.objects.update_or_create(
        site=site,
        defaults={"allow_signups": True},  # per-site allows signups
    )

    request = RequestFactory().get("/")
    assert AccountAdapter().is_open_for_signup(request) is True


@pytest.mark.django_db
def test_policy_can_disable_when_global_allows(mock_site_context, settings, site):
    """Per-site SiteSignupPolicy can disable signups even if the global setting allows them."""
    settings.ALLOW_SIGN_UPS = True  # global signups are allowed

    SiteSignupPolicy.objects.update_or_create(
        site=site,
        defaults={"allow_signups": False},  # per-site signups are not allowed
    )

    request = RequestFactory().get("/")
    assert AccountAdapter().is_open_for_signup(request) is False


@pytest.mark.django_db
def test_is_open_for_signup_respects_force_site_name(settings):
    """is_open_for_signup should use the forced site's policy, not the request domain's."""
    forced_site = SiteFactory(name="ForcedSite", domain="forced.example.com")
    SiteFactory(name="DomainSite", domain="testserver")

    SiteSignupPolicyFactory(site=forced_site, allow_signups=False)
    settings.ALLOW_SIGN_UPS = True  # global default allows signups

    request = RequestFactory().get("/")  # domain = testserver

    with override_settings(FORCE_SITE_NAME="ForcedSite"):
        if hasattr(request, _CACHED_SITE_ATTR):
            delattr(request, _CACHED_SITE_ATTR)
        result = AccountAdapter().is_open_for_signup(request)

    assert result is False  # Should use ForcedSite's policy (disallow), not DomainSite


@pytest.mark.django_db
def test_is_open_for_signup_uses_the_request_site_when_another_site_is_ambient(
    settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The request's own site decides, not whatever site the thread is holding.

    The lookup already knows which site it wants, so a leftover thread-local
    request pointing somewhere else must not be able to hide the policy row and
    quietly demote the answer to the global default.
    """
    policy_site = SiteFactory(name="PolicySite", domain="policy.example.com")
    ambient_site = SiteFactory(name="AmbientSite", domain="ambient.example.com")
    SiteSignupPolicyFactory(site=policy_site, allow_signups=False)
    settings.ALLOW_SIGN_UPS = True

    ambient_request = RequestFactory().get("/")
    setattr(ambient_request, _CACHED_SITE_ATTR, ambient_site)
    monkeypatch.setattr(_thread_locals, "request", ambient_request, raising=False)

    request = RequestFactory().get("/")
    setattr(request, _CACHED_SITE_ATTR, policy_site)

    assert AccountAdapter().is_open_for_signup(request) is False


# Tests for webhook and analytics events fired from the accounts app.


def _request_with_session() -> HttpRequest:
    request = RequestFactory().post("/accounts/signup/")
    SessionMiddleware(lambda r: HttpResponse()).process_request(request)
    return request


# transaction=True so that on_commit hooks for webhook event delivery fire under test
@pytest.mark.django_db(transaction=True)
class TestUserRegisteredWebhookEvent:
    def test_save_user_fires_webhook_event_on_commit(
        self, mock_site_context: object, mocker: object
    ) -> None:
        """When save_user is called with commit=True, fire_webhook_event is called."""
        mock_fire = mocker.patch("freedom_ls.webhooks.events.fire_webhook_event")
        adapter = AccountAdapter()
        user = UserFactory.build()

        mock_form = mocker.Mock()

        with patch(
            "allauth.account.adapter.DefaultAccountAdapter.save_user",
            return_value=user,
        ) as mock_super_save:
            result = adapter.save_user(
                _request_with_session(), user, mock_form, commit=True
            )

        mock_super_save.assert_called_once()
        mock_fire.assert_called_once_with(
            "user.registered",
            {
                "user_id": user.pk,
                "user_email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
            },
        )
        assert result is user

    def test_save_user_does_not_fire_webhook_without_commit(
        self, mock_site_context: object, mocker: object
    ) -> None:
        """When save_user is called with commit=False, no webhook event is fired."""
        mock_fire = mocker.patch("freedom_ls.webhooks.events.fire_webhook_event")
        adapter = AccountAdapter()
        user = UserFactory.build()

        mock_form = mocker.Mock()

        with patch(
            "allauth.account.adapter.DefaultAccountAdapter.save_user",
            return_value=user,
        ):
            adapter.save_user(_request_with_session(), user, mock_form, commit=False)

        mock_fire.assert_not_called()


@pytest.mark.django_db(transaction=True)
class TestSignUpAnalyticsEvent:
    def test_save_user_records_the_sign_up_event_on_commit(
        self, mock_site_context: object, mocker: object
    ) -> None:
        mocker.patch("freedom_ls.webhooks.events.fire_webhook_event")
        adapter = AccountAdapter()
        user = UserFactory.build()
        mock_form = mocker.Mock()
        request = _request_with_session()

        with patch(
            "allauth.account.adapter.DefaultAccountAdapter.save_user",
            return_value=user,
        ):
            adapter.save_user(request, user, mock_form, commit=True)

        assert request.session["google_analytics_events"] == [
            {"name": "sign_up", "params": {"method": "email"}}
        ]

    def test_save_user_does_not_record_the_event_without_commit(
        self, mock_site_context: object, mocker: object
    ) -> None:
        mocker.patch("freedom_ls.webhooks.events.fire_webhook_event")
        adapter = AccountAdapter()
        user = UserFactory.build()
        mock_form = mocker.Mock()
        request = _request_with_session()

        with patch(
            "allauth.account.adapter.DefaultAccountAdapter.save_user",
            return_value=user,
        ):
            adapter.save_user(request, user, mock_form, commit=False)

        assert "google_analytics_events" not in request.session
