"""System checks for the accounts app."""

from __future__ import annotations

from typing import Any

from django.core.checks import Tags, Warning, register


@register(Tags.security)
def check_legal_docs_present_when_required(
    app_configs: Any, **kwargs: Any
) -> list[Warning]:
    """Warn for any SiteSignupPolicy with `require_terms_acceptance=True`
    where the relevant `terms.md` / `privacy.md` cannot be resolved.
    """
    warnings: list[Warning] = []

    # Imports are local to avoid touching the app registry / DB at import time.
    from django.db.utils import DatabaseError, OperationalError, ProgrammingError

    from .legal_docs import has_legal_doc
    from .models import SiteSignupPolicy

    try:
        policies = list(
            SiteSignupPolicy.objects.select_related("site").filter(
                require_terms_acceptance=True
            )
        )
    except (DatabaseError, OperationalError, ProgrammingError):
        # The DB may not be ready (initial migrate, etc.). Stay silent.
        return warnings

    for policy in policies:
        for doc_type in ("terms", "privacy"):
            if not has_legal_doc(policy.site, doc_type):
                warnings.append(
                    Warning(
                        (
                            f"Site {policy.site.domain!r} has "
                            f"require_terms_acceptance=True but no resolvable "
                            f"{doc_type}.md (neither site-specific nor "
                            f"_default/). Signup will not collect this consent."
                        ),
                        id="freedom_ls_accounts.W001",
                    )
                )

    return warnings
