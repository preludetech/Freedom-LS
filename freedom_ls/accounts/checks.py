"""System checks for the accounts app."""

from __future__ import annotations

from typing import Any

from django.core.checks import Tags, Warning, register


@register(Tags.compatibility)
def check_email_colour_tokens(app_configs: Any, **kwargs: Any) -> list[Warning]:
    """Warn for any email colour token that is missing or cannot be resolved to hex.

    Re-resolves the seven email colour tokens from the active theme's theme.css,
    reusing the email_utils helpers. Returns a Warning for each token that is
    absent or produces an unresolvable value. Degrades gracefully when
    theme.css is missing — the check never raises.
    """
    from django.conf import settings

    from .email_utils import (
        EMAIL_COLOR_TOKENS,
        ColorResolveError,
        parse_tailwind_tokens,
        resolve_css_color,
    )

    warnings: list[Warning] = []

    css_path: str = getattr(settings, "EMAIL_THEME_CSS_PATH", "")

    try:
        token_map = parse_tailwind_tokens(css_path)
    except FileNotFoundError:
        # Theme CSS not yet generated (e.g. fresh checkout before
        # write_active_theme_css has run). Stay silent rather than crashing.
        return warnings

    for token, _fallback in EMAIL_COLOR_TOKENS:
        raw = token_map.get(f"color-{token}")
        if raw is None:
            warnings.append(
                Warning(
                    f"Email colour token --color-{token} is missing from "
                    f"{css_path!r}. The hardcoded fallback {_fallback!r} will be used.",
                    id="freedom_ls_accounts.W002",
                )
            )
            continue
        try:
            resolve_css_color(raw, token_map)
        except (ColorResolveError, ValueError) as exc:
            warnings.append(
                Warning(
                    f"Email colour token --color-{token}={raw!r} could not be "
                    f"resolved to a hex colour ({exc}). The hardcoded fallback "
                    f"{_fallback!r} will be used.",
                    id="freedom_ls_accounts.W002",
                )
            )

    return warnings


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
