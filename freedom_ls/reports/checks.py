"""Django system checks for the reports app.

E001 — A required reports setting the project must supply is unset. Currently
       none of the settings this app declares are required, so this returns
       nothing today; it costs one line and keeps the app honest if a
       required setting is added later.
W001 — REPORTS_STORAGE_ALIAS does not name a key in settings.STORAGES, so
       reports fall back to the default storage, which may be a publicly
       served MEDIA_ROOT.
W002 — The compiled Tailwind bundle can't be resolved through the staticfiles
       finders, so a report render will fail. The other half of this "fail
       loudly" pair is the render-time exception raised when the bundle is
       actually read.
W003 — Retired. Do not reuse the id: a project may still be silencing it.
W004 — A face named by REPORTS_FONT_FACES can't be resolved through the
       staticfiles finders. Same shape as W002, and for the same reason: a
       project that repoints the font faces at its own brand should learn
       about a typo from `manage.py check`, not from a failed report.
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
def check_report_font_faces_resolvable(**kwargs: object) -> list[CheckMessage]:
    """W004: Warn for every REPORTS_FONT_FACES path the finders can't resolve."""
    from freedom_ls.reports.config import config

    return [
        Warning(
            f"Report font face {face.get('family')!r} names "
            f"{face.get('static_path')!r}, which could not be resolved through "
            f"the staticfiles finders. Reports will fail to render.",
            hint=(
                "Correct the static_path in REPORTS_FONT_FACES, or add the font "
                "file to a static directory the finders search."
            ),
            id="freedom_ls_reports.W004",
        )
        for face in config.REPORTS_FONT_FACES
        if not _font_face_resolves(face)
    ]


def _font_face_resolves(face: dict[str, str]) -> bool:
    """Whether a face entry names a static path the finders can resolve."""
    static_path = face.get("static_path")
    if not static_path:
        return False
    return finders.find(static_path) is not None
