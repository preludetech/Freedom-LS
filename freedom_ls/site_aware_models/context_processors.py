"""Context processors for site-aware functionality."""

from django.conf import settings

from .config import config
from .models import get_cached_site


def site_config(request):
    """
    Add site configuration to template context.
    Makes site_title and site_name available in all templates.
    """
    site = get_cached_site(request)
    site_name = site.name

    # Get site-specific configuration from settings.site_conf
    site_conf = getattr(settings, "site_conf", {})
    site_conf_entry = site_conf.get(site_name, {})

    site_title = site_conf_entry.get("SITE_TITLE", site_name)

    return {
        "site_name": site_name,
        "site_title": site_title,
        "site_header": site_conf_entry.get("SITE_HEADER", site_name),
        "header_logo_static_path": config.HEADER_LOGO_STATIC_PATH,
        "favicon_static_path": config.FAVICON_STATIC_PATH,
        "header_title": config.HEADER_TITLE or site_title,
        "header_title_style": config.HEADER_TITLE_STYLE,
    }
