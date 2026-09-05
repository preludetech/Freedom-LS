from dataclasses import asdict

from allauth.account import app_settings as allauth_account_settings
from allauth.account.adapter import DefaultAccountAdapter
from allauth.core import context as allauth_context

from django.conf import settings
from django.contrib.sites.models import Site
from django.contrib.sites.requests import RequestSite
from django.http import HttpRequest
from django.templatetags.static import static
from django.utils.encoding import force_str

from freedom_ls.accounts.email_utils import (
    email_logo_dimensions,
    get_email_theme,
    resolved_email_logo_path,
)
from freedom_ls.base.email_encoding import set_8bit_encoding
from freedom_ls.site_aware_models.models import (
    get_cached_site,
    site_display_name,
    site_display_name_for_request,
)

from .config import config
from .models import SiteSignupPolicy, User


class AccountAdapter(DefaultAccountAdapter):
    def send_mail(self, template_prefix: str, email: str, context: dict) -> None:
        # Mirrors DefaultAccountAdapter.send_mail() but adds 8bit encoding and
        # injects email_logo_url / email_label for branded email templates.
        # If upgrading allauth, verify this stays in sync with the parent.
        request = allauth_context.request
        current_site = get_cached_site(request)

        # asdict(get_email_theme()) keys match the email-template contract
        # (color_primary, font_family, button_radius, ...). Both the branding
        # and theme work happen here so they run only when an email is actually
        # sent, not on every web request.
        ctx = {
            "request": request,
            "email": email,
            "current_site": current_site,
            **self._email_branding_context(request, current_site),
            **asdict(get_email_theme()),
        }
        ctx.update(context)
        msg = self.render_mail(template_prefix, email, ctx)
        set_8bit_encoding(msg)
        msg.send()

    def format_email_subject(self, subject: str) -> str:
        """Prefix the subject with the tenant's display name.

        DefaultAccountAdapter prefixes with the raw ``Site.name`` resolved from
        the HTTP host. Both halves are wrong here. The name disagrees with the
        body, which is HEADER_TITLE-first, and on an installation whose Site row
        was never given a display name that name is the bare domain. The host
        lookup ignores FORCE_SITE_NAME, so a pinned single-tenant install could
        be named after whichever host the mail happened to be triggered from.
        """
        prefix: str | None = allauth_account_settings.EMAIL_SUBJECT_PREFIX
        if prefix is None:
            name = site_display_name_for_request(allauth_context.request)
            prefix = f"[{name}] "
        return prefix + force_str(subject)

    def _email_branding_context(
        self, request: HttpRequest | None, current_site: Site | RequestSite
    ) -> dict[str, object]:
        """Build the logo + label context shared by all branded emails."""
        logo_path = resolved_email_logo_path()
        email_logo_url = self._resolve_email_logo_url(logo_path, request, current_site)

        # Size the logo from its real dimensions so its aspect ratio is never
        # stretched. None when the file can't be measured — the template then
        # falls back to a height-only constraint.
        email_logo_width: int | None = None
        email_logo_height: int | None = None
        if email_logo_url is not None and logo_path is not None:
            dimensions = email_logo_dimensions(logo_path)
            if dimensions is not None:
                email_logo_width, email_logo_height = dimensions

        return {
            "email_logo_url": email_logo_url,
            "email_label": site_display_name(current_site),
            "email_logo_width": email_logo_width,
            "email_logo_height": email_logo_height,
        }

    def _resolve_email_logo_url(
        self,
        logo_path: str | None,
        request: HttpRequest | None,
        current_site: Site | RequestSite,
    ) -> str | None:
        """Resolve the branded logo to an absolute URL, or None when absent.

        static() raises ValueError under ManifestStaticFilesStorage when the
        asset is absent from the manifest. The branded logo is best-effort, so
        a lookup failure degrades to the text label rather than aborting the
        whole transactional email.
        """
        try:
            static_url = static(logo_path) if logo_path else None
        except ValueError:
            static_url = None
        if static_url is None:
            return None
        if static_url.startswith(("http://", "https://")):
            # STATIC_URL is already absolute (e.g. a CDN); use it verbatim
            # rather than prefixing it with another scheme/host.
            return static_url
        if request is not None:
            # Reuse the request-based absolute URI (same as allauth's action
            # links) so the logo resolves wherever the email was triggered.
            return request.build_absolute_uri(static_url)
        # No request (e.g. mail sent outside a web request): fall back to the
        # canonical Site domain + configured protocol.
        protocol = getattr(settings, "ACCOUNT_DEFAULT_HTTP_PROTOCOL", "https")
        return f"{protocol}://{current_site.domain}{static_url}"

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
        If no policy exists for the current site, fall back to config.ALLOW_SIGN_UPS.
        """
        default_allow = config.ALLOW_SIGN_UPS

        # If there's no request (rare, but possible), use the global default.
        if request is None:
            return default_allow

        current_site = get_cached_site(request)
        if not isinstance(current_site, Site):
            return default_allow

        # _base_manager, not the site-aware `objects`: current_site is already
        # resolved from this request, and the site-aware manager would AND a
        # second site read from the ambient thread-local request. That request
        # is not always for the same site, and a mismatch hides the row rather
        # than erroring, silently demoting the answer to the global default.
        try:
            policy = SiteSignupPolicy._base_manager.get(site=current_site)
            return policy.allow_signups
        except SiteSignupPolicy.DoesNotExist:
            return default_allow
