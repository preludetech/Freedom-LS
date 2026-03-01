"""Integration tests for email templates.

Tests that all email templates render correctly with appropriate context,
contain expected content, and meet size constraints.
"""

import pytest

from django.conf import settings
from django.template.loader import render_to_string

from freedom_ls.accounts.factories import UserFactory

# Base context shared by all email templates
EMAIL_SETTINGS_CONTEXT: dict[str, str | None] = {
    "email_color_primary": settings.EMAIL_COLOR_PRIMARY,
    "email_color_foreground": settings.EMAIL_COLOR_FOREGROUND,
    "email_color_muted": settings.EMAIL_COLOR_MUTED,
    "email_font_family": settings.EMAIL_FONT_FAMILY,
    "email_logo_static_path": settings.EMAIL_LOGO_STATIC_PATH,
}

# Security context for notification emails
SECURITY_CONTEXT: dict[str, str] = {
    "ip": "192.168.1.100",
    "user_agent": "Mozilla/5.0 TestBrowser",
    "timestamp": "2026-03-01 12:00:00 UTC",
}

# Max allowed size for rendered HTML emails
MAX_EMAIL_SIZE_BYTES = 102_400  # 100KB


@pytest.fixture
def base_context(mock_site_context: object) -> dict[str, object]:
    """Provide base context for rendering email templates."""
    return {
        **EMAIL_SETTINGS_CONTEXT,
        "current_site": mock_site_context,
    }


# ---------------------------------------------------------------------------
# 1. Base template rendering tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestBaseEmailTemplate:
    """Tests for emails/base_email.html base template."""

    def test_base_email_contains_table_layout(
        self, base_context: dict[str, object]
    ) -> None:
        """Base email should use table-based layout with role=presentation."""
        html = render_to_string("emails/base_email.html", base_context)
        assert 'role="presentation"' in html

    def test_base_email_contains_brand_colors(
        self, base_context: dict[str, object]
    ) -> None:
        """Base email should include the primary brand color."""
        html = render_to_string("emails/base_email.html", base_context)
        assert settings.EMAIL_COLOR_PRIMARY in html

    def test_base_email_contains_site_name(
        self, base_context: dict[str, object]
    ) -> None:
        """Base email should display the site name."""
        html = render_to_string("emails/base_email.html", base_context)
        assert "TestSite" in html

    def test_base_email_footer_contains_copyright(
        self, base_context: dict[str, object]
    ) -> None:
        """Base email footer should contain a copyright symbol."""
        html = render_to_string("emails/base_email.html", base_context)
        # The &copy; entity or the actual copyright symbol should be present
        assert "&copy;" in html or "\u00a9" in html

    def test_base_email_size_under_limit(self, base_context: dict[str, object]) -> None:
        """Base email HTML should be under 100KB."""
        html = render_to_string("emails/base_email.html", base_context)
        assert len(html.encode("utf-8")) < MAX_EMAIL_SIZE_BYTES


# ---------------------------------------------------------------------------
# 2. Notification template rendering tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestNotificationBaseTemplate:
    """Tests for emails/base_notification_email.html."""

    def test_notification_contains_security_information_heading(
        self, base_context: dict[str, object]
    ) -> None:
        """Notification email should include Security Information section."""
        context = {**base_context, **SECURITY_CONTEXT}
        html = render_to_string("emails/base_notification_email.html", context)
        assert "Security Information" in html

    def test_notification_contains_ip_address(
        self, base_context: dict[str, object]
    ) -> None:
        """Notification email should display the IP address."""
        context = {**base_context, **SECURITY_CONTEXT}
        html = render_to_string("emails/base_notification_email.html", context)
        assert "192.168.1.100" in html

    def test_notification_contains_user_agent(
        self, base_context: dict[str, object]
    ) -> None:
        """Notification email should display the browser/user agent."""
        context = {**base_context, **SECURITY_CONTEXT}
        html = render_to_string("emails/base_notification_email.html", context)
        assert "Mozilla/5.0 TestBrowser" in html

    def test_notification_contains_timestamp(
        self, base_context: dict[str, object]
    ) -> None:
        """Notification email should display the timestamp."""
        context = {**base_context, **SECURITY_CONTEXT}
        html = render_to_string("emails/base_notification_email.html", context)
        assert "2026-03-01 12:00:00 UTC" in html


# ---------------------------------------------------------------------------
# 3. Allauth email type rendering tests (parametrized)
# ---------------------------------------------------------------------------

# Each tuple: (template_name, extra_context, expected_html_snippets, expected_txt_snippets, expected_subject)
ALLAUTH_EMAIL_TYPES: list[tuple[str, dict[str, str], list[str], list[str], str]] = [
    (
        "email_confirmation",
        {
            "activate_url": "https://testsite/confirm/abc123",
            "key": "abc123",  # pragma: allowlist secret
        },
        ["https://testsite/confirm/abc123", "Confirm Email Address"],
        ["https://testsite/confirm/abc123", "Confirm Email Address"],
        "Confirm your email address",
    ),
    (
        "email_confirmation_signup",
        {
            "activate_url": "https://testsite/confirm/signup456",
            "key": "signup456",  # pragma: allowlist secret
        },
        ["https://testsite/confirm/signup456", "Confirm Email Address"],
        ["https://testsite/confirm/signup456", "Confirm Email Address"],
        "Confirm your email address",
    ),
    (
        "password_reset_key",
        {
            "password_reset_url": "https://testsite/reset/key789",  # pragma: allowlist secret
        },
        ["https://testsite/reset/key789", "Reset Password"],
        ["https://testsite/reset/key789", "Reset Password"],
        "Reset your password",
    ),
    (
        "unknown_account",
        {
            "email": "unknown@example.com",
            "signup_url": "https://testsite/signup",
        },
        ["unknown@example.com", "https://testsite/signup", "Create an Account"],
        ["unknown@example.com", "https://testsite/signup", "Create an Account"],
        "Password reset request",
    ),
    (
        "login_code",
        {
            "code": "847293",
            "email": "user@example.com",
        },
        ["847293"],
        ["847293"],
        "Your login code",
    ),
    (
        "account_already_exists",
        {
            "email": "existing@example.com",
            "password_reset_url": "https://testsite/reset",  # pragma: allowlist secret
            "signup_url": "https://testsite/signup",
        },
        ["existing@example.com", "https://testsite/reset", "Reset Password"],
        ["existing@example.com", "https://testsite/reset", "Reset Password"],
        "Account already exists",
    ),
]

NOTIFICATION_EMAIL_TYPES: list[
    tuple[str, dict[str, str], list[str], list[str], str]
] = [
    (
        "password_changed",
        {},
        ["password has been changed"],
        ["password has been changed"],
        "Your password has been changed",
    ),
    (
        "password_set",
        {},
        ["password has been set"],
        ["password has been set"],
        "A password has been set for your account",
    ),
    (
        "email_changed",
        {
            "from_email": "old@example.com",
            "to_email": "new@example.com",
        },
        ["old@example.com", "new@example.com", "email address has been changed"],
        ["old@example.com", "new@example.com", "email address has been changed"],
        "Your email address has been changed",
    ),
    (
        "email_confirm",
        {},
        ["email address has been confirmed"],
        ["email address has been confirmed"],
        "Your email address has been confirmed",
    ),
    (
        "email_deleted",
        {
            "deleted_email": "removed@example.com",
        },
        ["removed@example.com", "has been removed"],
        ["removed@example.com", "has been removed"],
        "An email address has been removed from your account",
    ),
]


@pytest.mark.django_db
class TestAllauthMessageEmails:
    """Tests for allauth message-type email templates (non-notification)."""

    @pytest.mark.parametrize(
        (
            "template_name",
            "extra_context",
            "expected_html_snippets",
            "expected_txt_snippets",
            "expected_subject",
        ),
        ALLAUTH_EMAIL_TYPES,
        ids=[t[0] for t in ALLAUTH_EMAIL_TYPES],
    )
    def test_html_template_renders_with_expected_content(
        self,
        base_context: dict[str, object],
        template_name: str,
        extra_context: dict[str, str],
        expected_html_snippets: list[str],
        expected_txt_snippets: list[str],
        expected_subject: str,
    ) -> None:
        """HTML message template should render and contain expected content."""
        user = UserFactory(first_name="Alice", last_name="Smith")
        context = {**base_context, "user": user, **extra_context}
        html = render_to_string(f"account/email/{template_name}_message.html", context)

        assert html.strip(), f"HTML template for {template_name} rendered empty"
        for snippet in expected_html_snippets:
            assert snippet in html, (
                f"Expected '{snippet}' in {template_name} HTML output"
            )

    @pytest.mark.parametrize(
        (
            "template_name",
            "extra_context",
            "expected_html_snippets",
            "expected_txt_snippets",
            "expected_subject",
        ),
        ALLAUTH_EMAIL_TYPES,
        ids=[t[0] for t in ALLAUTH_EMAIL_TYPES],
    )
    def test_txt_template_renders_with_expected_content(
        self,
        base_context: dict[str, object],
        template_name: str,
        extra_context: dict[str, str],
        expected_html_snippets: list[str],
        expected_txt_snippets: list[str],
        expected_subject: str,
    ) -> None:
        """Text message template should render and contain expected content."""
        user = UserFactory(first_name="Alice", last_name="Smith")
        context = {**base_context, "user": user, **extra_context}
        txt = render_to_string(f"account/email/{template_name}_message.txt", context)

        assert txt.strip(), f"Text template for {template_name} rendered empty"
        for snippet in expected_txt_snippets:
            assert snippet in txt, (
                f"Expected '{snippet}' in {template_name} text output"
            )

    @pytest.mark.parametrize(
        (
            "template_name",
            "extra_context",
            "expected_html_snippets",
            "expected_txt_snippets",
            "expected_subject",
        ),
        ALLAUTH_EMAIL_TYPES,
        ids=[t[0] for t in ALLAUTH_EMAIL_TYPES],
    )
    def test_subject_line_is_correct(
        self,
        base_context: dict[str, object],
        template_name: str,
        extra_context: dict[str, str],
        expected_html_snippets: list[str],
        expected_txt_snippets: list[str],
        expected_subject: str,
    ) -> None:
        """Subject line template should render the correct subject text."""
        context = {**base_context, **extra_context}
        subject = render_to_string(
            f"account/email/{template_name}_subject.txt", context
        ).strip()
        assert subject == expected_subject


@pytest.mark.django_db
class TestAllauthNotificationEmails:
    """Tests for allauth notification-type email templates (with security info)."""

    @pytest.mark.parametrize(
        (
            "template_name",
            "extra_context",
            "expected_html_snippets",
            "expected_txt_snippets",
            "expected_subject",
        ),
        NOTIFICATION_EMAIL_TYPES,
        ids=[t[0] for t in NOTIFICATION_EMAIL_TYPES],
    )
    def test_html_notification_renders_with_expected_content(
        self,
        base_context: dict[str, object],
        template_name: str,
        extra_context: dict[str, str],
        expected_html_snippets: list[str],
        expected_txt_snippets: list[str],
        expected_subject: str,
    ) -> None:
        """HTML notification template should render and contain expected content."""
        user = UserFactory(first_name="Alice", last_name="Smith")
        context = {
            **base_context,
            "user": user,
            **SECURITY_CONTEXT,
            **extra_context,
        }
        html = render_to_string(f"account/email/{template_name}_message.html", context)

        assert html.strip(), f"HTML template for {template_name} rendered empty"
        for snippet in expected_html_snippets:
            assert snippet in html, (
                f"Expected '{snippet}' in {template_name} HTML output"
            )

    @pytest.mark.parametrize(
        (
            "template_name",
            "extra_context",
            "expected_html_snippets",
            "expected_txt_snippets",
            "expected_subject",
        ),
        NOTIFICATION_EMAIL_TYPES,
        ids=[t[0] for t in NOTIFICATION_EMAIL_TYPES],
    )
    def test_txt_notification_renders_with_expected_content(
        self,
        base_context: dict[str, object],
        template_name: str,
        extra_context: dict[str, str],
        expected_html_snippets: list[str],
        expected_txt_snippets: list[str],
        expected_subject: str,
    ) -> None:
        """Text notification template should render and contain expected content."""
        user = UserFactory(first_name="Alice", last_name="Smith")
        context = {
            **base_context,
            "user": user,
            **SECURITY_CONTEXT,
            **extra_context,
        }
        txt = render_to_string(f"account/email/{template_name}_message.txt", context)

        assert txt.strip(), f"Text template for {template_name} rendered empty"
        for snippet in expected_txt_snippets:
            assert snippet in txt, (
                f"Expected '{snippet}' in {template_name} text output"
            )

    @pytest.mark.parametrize(
        (
            "template_name",
            "extra_context",
            "expected_html_snippets",
            "expected_txt_snippets",
            "expected_subject",
        ),
        NOTIFICATION_EMAIL_TYPES,
        ids=[t[0] for t in NOTIFICATION_EMAIL_TYPES],
    )
    def test_notification_subject_line_is_correct(
        self,
        base_context: dict[str, object],
        template_name: str,
        extra_context: dict[str, str],
        expected_html_snippets: list[str],
        expected_txt_snippets: list[str],
        expected_subject: str,
    ) -> None:
        """Subject line for notification emails should be correct."""
        context = {**base_context, **extra_context}
        subject = render_to_string(
            f"account/email/{template_name}_subject.txt", context
        ).strip()
        assert subject == expected_subject

    @pytest.mark.parametrize(
        (
            "template_name",
            "extra_context",
            "expected_html_snippets",
            "expected_txt_snippets",
            "expected_subject",
        ),
        NOTIFICATION_EMAIL_TYPES,
        ids=[t[0] for t in NOTIFICATION_EMAIL_TYPES],
    )
    def test_notification_html_contains_security_info(
        self,
        base_context: dict[str, object],
        template_name: str,
        extra_context: dict[str, str],
        expected_html_snippets: list[str],
        expected_txt_snippets: list[str],
        expected_subject: str,
    ) -> None:
        """Notification HTML emails should include security information section."""
        user = UserFactory(first_name="Alice", last_name="Smith")
        context = {
            **base_context,
            "user": user,
            **SECURITY_CONTEXT,
            **extra_context,
        }
        html = render_to_string(f"account/email/{template_name}_message.html", context)

        assert "Security Information" in html
        assert SECURITY_CONTEXT["ip"] in html
        assert SECURITY_CONTEXT["user_agent"] in html
        assert SECURITY_CONTEXT["timestamp"] in html


# ---------------------------------------------------------------------------
# 4. Header logo test
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestHeaderLogo:
    """Tests for logo vs text rendering in the email header."""

    def test_header_shows_img_when_logo_path_is_set(
        self, base_context: dict[str, object]
    ) -> None:
        """When email_logo_static_path is set, header should contain an img tag."""
        context = {**base_context, "email_logo_static_path": "images/logo.png"}
        html = render_to_string("emails/base_email.html", context)
        assert "<img" in html

    def test_header_shows_site_name_when_no_logo(
        self, base_context: dict[str, object]
    ) -> None:
        """When email_logo_static_path is None, header should show site name as text."""
        context = {**base_context, "email_logo_static_path": None}
        html = render_to_string("emails/base_email.html", context)
        assert "TestSite" in html
        # The h1 tag should be present for text-based header
        assert "<h1" in html


# ---------------------------------------------------------------------------
# 5. Greeting personalization test
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGreetingPersonalization:
    """Tests for personalized greeting in emails."""

    def test_greeting_includes_first_name_when_present(
        self,
        base_context: dict[str, object],
    ) -> None:
        """Greeting should say 'Hi Alice,' when user has a first name."""
        user = UserFactory(first_name="Alice", last_name="Smith")
        context = {**base_context, "user": user}
        html = render_to_string("emails/base_email.html", context)
        assert "Hi Alice," in html

    def test_greeting_omits_name_when_no_first_name(
        self,
        base_context: dict[str, object],
    ) -> None:
        """Greeting should say 'Hi,' when user has no first name."""
        user = UserFactory(first_name="", last_name="")
        context = {**base_context, "user": user}
        html = render_to_string("emails/base_email.html", context)
        assert "Hi," in html
        # Should not have "Hi ," with extra space
        assert "Hi ," not in html


# ---------------------------------------------------------------------------
# 6. Size test for all HTML emails
# ---------------------------------------------------------------------------

ALL_HTML_TEMPLATES: list[tuple[str, dict[str, str]]] = [
    (
        "account/email/email_confirmation_message.html",
        {
            "activate_url": "https://example.com/confirm",
            "key": "abc",  # pragma: allowlist secret
        },
    ),
    (
        "account/email/email_confirmation_signup_message.html",
        {
            "activate_url": "https://example.com/confirm",
            "key": "abc",  # pragma: allowlist secret
        },
    ),
    (
        "account/email/password_reset_key_message.html",
        {"password_reset_url": "https://example.com/reset"},
    ),
    (
        "account/email/unknown_account_message.html",
        {"email": "test@example.com", "signup_url": "https://example.com/signup"},
    ),
    (
        "account/email/login_code_message.html",
        {"code": "123456", "email": "test@example.com"},
    ),
    (
        "account/email/account_already_exists_message.html",
        {
            "email": "test@example.com",
            "password_reset_url": "https://example.com/reset",
            "signup_url": "https://example.com/signup",
        },
    ),
    ("account/email/password_changed_message.html", {**SECURITY_CONTEXT}),
    ("account/email/password_set_message.html", {**SECURITY_CONTEXT}),
    (
        "account/email/email_changed_message.html",
        {
            "from_email": "old@example.com",
            "to_email": "new@example.com",
            **SECURITY_CONTEXT,
        },
    ),
    ("account/email/email_confirm_message.html", {**SECURITY_CONTEXT}),
    (
        "account/email/email_deleted_message.html",
        {"deleted_email": "removed@example.com", **SECURITY_CONTEXT},
    ),
]


@pytest.mark.django_db
class TestEmailSizeConstraints:
    """Tests that all rendered HTML emails stay under the 100KB limit."""

    @pytest.mark.parametrize(
        ("template_path", "extra_context"),
        ALL_HTML_TEMPLATES,
        ids=[
            t[0].split("/")[-1].replace("_message.html", "") for t in ALL_HTML_TEMPLATES
        ],
    )
    def test_html_email_under_100kb(
        self,
        base_context: dict[str, object],
        template_path: str,
        extra_context: dict[str, str],
    ) -> None:
        """Each HTML email template should render to less than 100KB."""
        user = UserFactory(first_name="Alice", last_name="Smith")
        context = {**base_context, "user": user, **extra_context}
        html = render_to_string(template_path, context)
        size = len(html.encode("utf-8"))
        assert size < MAX_EMAIL_SIZE_BYTES, (
            f"{template_path} rendered to {size} bytes, exceeding {MAX_EMAIL_SIZE_BYTES} byte limit"
        )
