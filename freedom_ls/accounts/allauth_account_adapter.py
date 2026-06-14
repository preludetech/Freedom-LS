import email.policy
from email.mime.base import MIMEBase

from allauth.account.adapter import DefaultAccountAdapter
from allauth.core import context as allauth_context

from django.conf import settings
from django.contrib.sites.models import Site
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import EmailMessage
from django.http import HttpRequest
from django.templatetags.static import static

from freedom_ls.accounts.email_utils import (
    email_logo_dimensions,
    resolved_email_logo_path,
)
from freedom_ls.site_aware_models.models import get_cached_site

from .models import SiteSignupPolicy, User


def _set_8bit_encoding(msg: EmailMessage) -> None:
    """Set Content-Transfer-Encoding to 8bit on an EmailMessage.

    Prevents Python's email library from using quoted-printable encoding,
    which wraps lines at 76 characters and corrupts long URLs.
    """
    original_message = msg.message

    def patched_message(
        *, policy: email.policy.Policy = email.policy.default
    ) -> MIMEBase:
        mime_msg: MIMEBase = original_message(policy=policy)
        for part in mime_msg.walk():
            if part.get_content_type() in ("text/plain", "text/html"):
                decoded_payload = part.get_payload(decode=True)
                if isinstance(decoded_payload, bytes):
                    charset = part.get_content_charset() or "utf-8"
                    del part["Content-Transfer-Encoding"]
                    part["Content-Transfer-Encoding"] = "8bit"
                    part.set_payload(decoded_payload.decode(charset), charset)
                    # set_payload with charset re-encodes, so override again
                    del part["Content-Transfer-Encoding"]
                    part["Content-Transfer-Encoding"] = "8bit"
        return mime_msg

    object.__setattr__(msg, "message", patched_message)


class AccountAdapter(DefaultAccountAdapter):
    def send_mail(self, template_prefix: str, email: str, context: dict) -> None:
        # Mirrors DefaultAccountAdapter.send_mail() but adds 8bit encoding and
        # injects email_logo_url / email_label for branded email templates.
        # If upgrading allauth, verify this stays in sync with the parent.
        request = allauth_context.request
        current_site = get_current_site(request)

        logo_path = resolved_email_logo_path()
        email_logo_url: str | None = None
        # static() raises ValueError under ManifestStaticFilesStorage when the
        # asset is absent from the manifest. The branded logo is best-effort, so
        # a lookup failure degrades to the text label rather than aborting the
        # whole transactional email.
        try:
            static_url = static(logo_path) if logo_path else None
        except ValueError:
            static_url = None
        if static_url is not None:
            if static_url.startswith(("http://", "https://")):
                # STATIC_URL is already absolute (e.g. a CDN); use it verbatim
                # rather than prefixing it with another scheme/host.
                email_logo_url = static_url
            elif request is not None:
                # Reuse the request-based absolute URI (same as allauth's action
                # links) so the logo resolves wherever the email was triggered.
                email_logo_url = request.build_absolute_uri(static_url)
            else:
                # No request (e.g. mail sent outside a web request): fall back to
                # the canonical Site domain + configured protocol.
                protocol = getattr(settings, "ACCOUNT_DEFAULT_HTTP_PROTOCOL", "https")
                email_logo_url = f"{protocol}://{current_site.domain}{static_url}"
        email_label: str = settings.HEADER_TITLE or current_site.name

        # Size the logo from its real dimensions so its aspect ratio is never
        # stretched. None when the file can't be measured — the template then
        # falls back to a height-only constraint.
        logo_dimensions = (
            email_logo_dimensions(logo_path)
            if email_logo_url is not None and logo_path is not None
            else None
        )
        email_logo_width: int | None = None
        email_logo_height: int | None = None
        if logo_dimensions is not None:
            email_logo_width, email_logo_height = logo_dimensions

        ctx = {
            "request": request,
            "email": email,
            "current_site": current_site,
            "email_logo_url": email_logo_url,
            "email_label": email_label,
            "email_logo_width": email_logo_width,
            "email_logo_height": email_logo_height,
        }
        ctx.update(context)
        msg = self.render_mail(template_prefix, email, ctx)
        _set_8bit_encoding(msg)
        msg.send()

    def save_user(
        self,
        request: HttpRequest,
        user: User,
        form: object,
        commit: bool = True,
    ) -> User:
        user = super().save_user(request, user, form, commit=commit)
        if commit:
            from freedom_ls.webhooks.events import fire_webhook_event

            fire_webhook_event(
                "user.registered",
                {
                    "user_id": user.pk,
                    "user_email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                },
            )
        return user

    def send_notification_mail(
        self,
        template_prefix: str,
        user: User,
        context: dict | None = None,
        email: str | None = None,
    ) -> None:
        context = context or {}
        context["user"] = user
        super().send_notification_mail(template_prefix, user, context, email=email)

    def is_open_for_signup(self, request):
        """
        Signup is controlled per-site via accounts.SiteSignupPolicy.
        If no policy exists for the current site, fall back to settings.ALLOW_SIGN_UPS.
        """
        default_allow = getattr(settings, "ALLOW_SIGN_UPS", True)

        # If there's no request (rare, but possible), use the global default.
        if request is None:
            return default_allow

        current_site = get_cached_site(request)
        if not isinstance(current_site, Site):
            return default_allow

        try:
            policy = SiteSignupPolicy.objects.get(site=current_site)
            return policy.allow_signups
        except SiteSignupPolicy.DoesNotExist:
            return default_allow
