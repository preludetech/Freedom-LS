from functools import cache
from importlib import import_module

from django.conf import settings
from django.contrib.sites.models import Site

from freedom_ls.role_based_permissions.types import SiteRolesConfig


@cache
def get_role_config(site_name: str | None = None) -> SiteRolesConfig:
    """
    Load the role config for the given site name.

    Uses FREEDOMLS_PERMISSIONS_MODULES (a dict mapping site names to module paths).
    Falls back to freedom_ls.role_based_permissions.roles if no site-specific config exists.
    """
    if site_name is None:
        site_name = Site.objects.get_current().name

    modules: dict[str, str] = getattr(settings, "FREEDOMLS_PERMISSIONS_MODULES", {})
    module_path = modules.get(site_name, "freedom_ls.role_based_permissions.roles")
    module = import_module(module_path)
    if hasattr(module, "ROLES"):
        config: SiteRolesConfig = module.ROLES
    elif hasattr(module, "BASE_ROLES"):
        config = module.BASE_ROLES
    else:
        raise ImportError(
            f"Module '{module_path}' has neither 'ROLES' nor 'BASE_ROLES' attribute"
        )
    return config
