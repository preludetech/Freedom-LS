"""System checks for the accounts app."""

from __future__ import annotations

from typing import Any

from django.core.checks import Tags, Warning, register


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
    from django.conf import settings
    from django.contrib.sites.models import Site
    from django.db.utils import DatabaseError, OperationalError, ProgrammingError

    from .legal_docs import has_legal_doc
    from .models import SiteSignupPolicy

    default_require = getattr(settings, "REQUIRE_TERMS_ACCEPTANCE", False)

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
        requires = (
            policy.require_terms_acceptance if policy is not None else default_require
        )
        if not requires:
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
