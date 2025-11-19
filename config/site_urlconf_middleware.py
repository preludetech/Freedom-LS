from django.contrib.sites.shortcuts import get_current_site
from django.urls import include, path
from config.urls import urlpatterns as base_urlpatterns


class SiteURLConfMiddleware:
    """
    Middleware that dynamically sets URLconf based on the current site.

    This allows different sites to use different root URL configurations
    while sharing common URLs (admin, accounts, educator, etc.).

    Configuration: Update SITE_URLCONFS dict below to map site names to app URLs.
    """

    # TODO: Update these mappings when you create bloom and prelude apps
    SITE_URLCONFS = {
        # "Wrend": "student_interface.urls",
        "Bloom": "bloom_student_interface.urls",
        # "Prelude": "student_interface.urls",  # Change to "prelude.urls" when created
    }

    def __init__(self, get_response):
        self.get_response = get_response
        # Cache URLconf modules per site to avoid recreating them on every request
        self._urlconf_cache = {}

    def __call__(self, request):
        current_site = get_current_site(request)
        site_name = current_site.name

        # Get the site-specific URLconf module name
        site_urlconf = self.SITE_URLCONFS.get(site_name, "student_interface.urls")

        # Create a unique module name for this site's URLconf
        urlconf_module_name = f"_site_urlconf_{site_name.lower().replace(' ', '_')}"

        # Build the URLconf if not cached
        if urlconf_module_name not in self._urlconf_cache:
            # Create a module with urlpatterns that includes base + site-specific URLs
            import sys
            from types import ModuleType

            module = ModuleType(urlconf_module_name)
            module.urlpatterns = base_urlpatterns + [
                path("", include(site_urlconf)),
            ]
            sys.modules[urlconf_module_name] = module
            self._urlconf_cache[urlconf_module_name] = module

        # Set the URLconf for this request
        request.urlconf = urlconf_module_name

        response = self.get_response(request)
        return response
