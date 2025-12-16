"""Context processors for site-aware functionality."""

from django.contrib.sites.shortcuts import get_current_site
from django.conf import settings


def site_config(request):
    """
    Add site configuration to template context.
    Makes site_title and site_name available in all templates.
    """
    site = get_current_site(request)
    site_name = site.name

    # Get site-specific configuration from settings.site_conf
    site_conf = getattr(settings, 'site_conf', {})
    config = site_conf.get(site_name, {})

    return {
        'site_name': site_name,
        'site_title': config.get('SITE_TITLE', site_name),
        'site_header': config.get('SITE_HEADER', site_name),
    }
