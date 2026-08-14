"""Django system checks for the reports app.

E001 — A required reports setting the project must supply is unset. Currently
       none of the three settings this app declares are required, so this
       returns nothing today; it costs one line and keeps the app honest if a
       required setting is added later.
W001 — REPORTS_STORAGE_ALIAS does not name a key in settings.STORAGES, so
       reports fall back to the default storage, which may be a publicly
       served MEDIA_ROOT.
W002 — The compiled Tailwind bundle can't be resolved through the staticfiles
       finders, so a report render will fail. The other half of this "fail
       loudly" pair is the render-time exception raised when the bundle is
       actually read.
W003 — REPORTS_AT_RISK_RULES_MODULE can't be imported, or exports neither
       AT_RISK_RULES nor BASE_AT_RISK_RULES, so a report generation would
       crash at run time instead of being caught at `manage.py check` time.
"""

from __future__ import annotations

from django.contrib.staticfiles import finders
from django.core.checks import CheckMessage, Warning, register

from freedom_ls.base.app_settings import required_settings_errors


@register()
def check_required_reports_settings(**kwargs: object) -> list[CheckMessage]:
    """E001: Report any required reports setting the project has not set."""
    from freedom_ls.reports.config import config

    return required_settings_errors(config, "freedom_ls_reports")


@register()
def check_reports_storage_alias_configured(**kwargs: object) -> list[CheckMessage]:
    """W001: Warn when REPORTS_STORAGE_ALIAS names no key in settings.STORAGES."""
    from django.conf import settings

    from freedom_ls.reports.config import config

    if config.REPORTS_STORAGE_ALIAS in settings.STORAGES:
        return []

    return [
        Warning(
            f"REPORTS_STORAGE_ALIAS={config.REPORTS_STORAGE_ALIAS!r} is not a key "
            f"in settings.STORAGES. Reports will fall back to the default "
            f"storage, which may be a publicly served MEDIA_ROOT.",
            hint="Declare a private storage alias in settings.STORAGES.",
            id="freedom_ls_reports.W001",
        )
    ]


@register()
def check_tailwind_bundle_resolvable(**kwargs: object) -> list[CheckMessage]:
    """W002: Warn when the compiled Tailwind bundle can't be found by the finders."""
    if finders.find("vendor/tailwind.output.css") is not None:
        return []

    return [
        Warning(
            "Compiled Tailwind bundle 'vendor/tailwind.output.css' could not be "
            "resolved through the staticfiles finders. Reports will fail to render.",
            hint="Run `npm run tailwind_build`.",
            id="freedom_ls_reports.W002",
        )
    ]


@register()
def check_at_risk_rules_module_configured(**kwargs: object) -> list[CheckMessage]:
    """W003: Warn when REPORTS_AT_RISK_RULES_MODULE can't resolve to a rule list."""
    from freedom_ls.reports.at_risk.loader import get_at_risk_rules
    from freedom_ls.reports.config import config

    try:
        get_at_risk_rules()
    except (ImportError, AttributeError):
        return [
            Warning(
                f"REPORTS_AT_RISK_RULES_MODULE={config.REPORTS_AT_RISK_RULES_MODULE!r} "
                f"could not be imported, or exports neither AT_RISK_RULES nor "
                f"BASE_AT_RISK_RULES.",
                hint=(
                    "Point REPORTS_AT_RISK_RULES_MODULE at a module exporting "
                    "AT_RISK_RULES or BASE_AT_RISK_RULES."
                ),
                id="freedom_ls_reports.W003",
            )
        ]

    return []
