from allauth.account.adapter import DefaultAccountAdapter

from django.conf import settings
from django.contrib.sites.models import Site

from freedom_ls.site_aware_models.models import get_cached_site

from .models import SiteSignupPolicy, User


class AccountAdapter(DefaultAccountAdapter):
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

        qs = SiteSignupPolicy.objects.filter(site=current_site)
        if qs.exists():
            return qs.get().allow_signups

        return default_allow
