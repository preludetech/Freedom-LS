from email.mime.base import MIMEBase

from allauth.account.adapter import DefaultAccountAdapter
from allauth.core import context as allauth_context

from django.conf import settings
from django.contrib.sites.models import Site
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import EmailMessage
from django.http import HttpRequest

from freedom_ls.site_aware_models.models import get_cached_site

from .models import SiteSignupPolicy, User


def _set_8bit_encoding(msg: EmailMessage) -> None:
    """Set Content-Transfer-Encoding to 8bit on an EmailMessage.

    Prevents Python's email library from using quoted-printable encoding,
    which wraps lines at 76 characters and corrupts long URLs.
    """
    original_message = msg.message

    def patched_message() -> MIMEBase:
        mime_msg: MIMEBase = original_message()
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
        # Mirrors DefaultAccountAdapter.send_mail() but adds 8bit encoding.
        # If upgrading allauth, verify this stays in sync with the parent.
        request = allauth_context.request
        ctx = {
            "request": request,
            "email": email,
            "current_site": get_current_site(request),
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
