from allauth.account.adapter import DefaultAccountAdapter
from django.contrib.sites.shortcuts import get_current_site
from .models import SiteSignupPolicy
from django.conf import settings


class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        """
        Signup is controlled per-site via accounts.SiteSignupPolicy.
        If no policy exists for the current site, fall back to settings.ALLOW_SIGN_UPS.
        """
        default_allow = getattr(settings, "ALLOW_SIGN_UPS", True)

        # If there's no request (rare, but possible), use the global default.
        if request is None:
            return default_allow

        site = get_current_site(request)

        qs = SiteSignupPolicy.objects.filter(site=site)
        if qs.exists():
            return qs.get().allow_signups

        return default_allow
