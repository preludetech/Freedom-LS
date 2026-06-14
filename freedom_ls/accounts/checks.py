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
    policy row and `settings.REQUIRE_TERMS_ACCEPTANCE` is True.
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
        policies_by_site_id = {
            p.site_id: p for p in SiteSignupPolicy.objects.select_related("site")
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
