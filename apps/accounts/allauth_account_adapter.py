from django.conf import settings
from allauth.account.adapter import DefaultAccountAdapter
from django.contrib.sites.shortcuts import get_current_site
from .models import SiteSignupPolicy


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

        allow = (
            SiteSignupPolicy.objects.filter(site=site)
            .values_list("allow_signups", flat=True)
            .first()
        )

        return default_allow if allow is None else bool(allow)
