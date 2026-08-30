"""System checks for the accounts app."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from django.apps import AppConfig
from django.core.checks import Error, Tags, Warning, register


@register(Tags.compatibility)
def check_email_colour_tokens(
    app_configs: Sequence[AppConfig] | None, **kwargs: object
) -> list[Error]:
    """Error for any email theme token that cannot be resolved from the theme.

    Builds the same merged token map ``get_email_theme`` uses — the default
    theme as a baseline with the active theme layered on top — and resolves
    every email token (colours, font, button radius), reusing the email_utils
    helpers. There is no hardcoded fallback, so an unresolvable token is an
    Error: it surfaces at deploy/startup before any email send raises. A token
    merely absent from the active theme is fine (the default theme supplies it).
    Stays silent if the default theme.css cannot be read yet (e.g. a fresh
    checkout) rather than crashing the check.
    """
    from .email_utils import (
        EMAIL_COLOR_ROLES,
        EmailThemeError,
        active_theme_css_path,
        default_theme_css_path,
        extract_button_radius,
        extract_font_family,
        parse_tailwind_tokens,
        resolve_color_token,
    )

    try:
        default_map = parse_tailwind_tokens(default_theme_css_path())
    except FileNotFoundError:
        return []
    try:
        active_map = parse_tailwind_tokens(active_theme_css_path())
    except FileNotFoundError:
        active_map = {}
    token_map = {**default_map, **active_map}

    errors: list[Error] = []
    for role, _field in EMAIL_COLOR_ROLES:
        try:
            resolve_color_token(token_map, role)
        except EmailThemeError as exc:
            errors.append(Error(str(exc), id="freedom_ls_accounts.E002"))
    for extractor in (extract_font_family, extract_button_radius):
        try:
            extractor(token_map)
        except EmailThemeError as exc:
            errors.append(Error(str(exc), id="freedom_ls_accounts.E002"))

    return errors


@register(Tags.security)
def check_legal_docs_present_when_required(
    app_configs: Any, **kwargs: Any
) -> list[Warning]:
    """Warn for any Site that effectively requires terms acceptance but where
    the relevant `terms.md` / `privacy.md` cannot be resolved.

    A site effectively requires terms acceptance when either it has a
    `SiteSignupPolicy` with `require_terms_acceptance=True`, or it has no
    policy row and `config.REQUIRE_TERMS_ACCEPTANCE` is True.
    """
    warnings: list[Warning] = []

    # Imports are local to avoid touching the app registry / DB at import time.
    from django.contrib.sites.models import Site
    from django.db.utils import DatabaseError, OperationalError, ProgrammingError

    from .legal_docs import has_legal_doc
    from .models import SiteSignupPolicy
    from .utils import get_effective_require_terms_acceptance

    try:
        sites = list(Site.objects.all())
        # _base_manager, not the site-aware `objects`: this check reports on
        # every Site, so it needs every policy row. The site-aware manager would
        # narrow the map to whatever site an ambient thread-local request points
        # at, and every other site would then be judged against the global
        # default instead of its own policy.
        policies_by_site_id = {
            p.site_id: p for p in SiteSignupPolicy._base_manager.select_related("site")
        }
    except (DatabaseError, OperationalError, ProgrammingError):
        # The DB may not be ready (initial migrate, etc.). Stay silent.
        return warnings

    for site in sites:
        policy = policies_by_site_id.get(site.id)
        if not get_effective_require_terms_acceptance(policy):
            continue
        for doc_type in ("terms", "privacy"):
            if not has_legal_doc(site, doc_type):
                warnings.append(
                    Warning(
                        (
                            f"Site {site.domain!r} has "
                            f"require_terms_acceptance=True but no resolvable "
                            f"{doc_type}.md (neither site-specific nor "
                            f"_default/). Signup will not collect this consent."
                        ),
                        id="freedom_ls_accounts.W001",
                    )
                )

    return warnings


@register(Tags.security)
def check_trusted_proxy_ip_header_is_not_a_meta_key(
    app_configs: Sequence[AppConfig] | None, **kwargs: object
) -> list[Error]:
    """E003: Error when TRUSTED_PROXY_IP_HEADER holds a request.META key.

    The setting used to name a key in request.META and now names the header
    itself, because both readers — get_client_ip here and allauth's own — go
    through request.headers. A carried-over "HTTP_X_FORWARDED_FOR" is not found
    there, so the lookup returns None and falls through to REMOTE_ADDR: the
    proxy's own address, written into LegalConsent evidence and used as half of
    every django-axes lockout key, with nothing to say it happened.

    An HTTP_ prefix is unambiguous — no real header carries one — so this is an
    Error rather than a Warning, and it runs outside --deploy so a downstream
    meets it on runserver rather than at deploy time.
    """
    from .config import config

    header_name = config.TRUSTED_PROXY_IP_HEADER
    if not header_name or not header_name.startswith("HTTP_"):
        return []
    plain_name = header_name.removeprefix("HTTP_").replace("_", "-").title()
    return [
        Error(
            f"TRUSTED_PROXY_IP_HEADER is {header_name!r}, which is a request.META "
            f"key. The setting now names the HTTP header itself, so this value "
            f"never matches and the client IP silently falls back to the "
            f"connecting address.",
            hint=f"Use the header name instead, e.g. {plain_name!r}.",
            id="freedom_ls_accounts.E003",
        )
    ]
