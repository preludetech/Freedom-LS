from __future__ import annotations

from freedom_ls.base.app_settings import AppSettings, Setting


class CourseAccessConfig(AppSettings):
    COURSE_ACCESS_BACKEND: str
    # DEV/STAGING ONLY — preview overrides. Never enable in production; a
    # DEBUG=False environment with either set True raises system check W001.
    OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE: bool
    OVERRIDE_COURSE_ACCESS_TO_FREE: bool

    declared_settings = {
        "COURSE_ACCESS_BACKEND": Setting(required=True),
        "OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE": Setting(default=False),
        "OVERRIDE_COURSE_ACCESS_TO_FREE": Setting(default=False),
    }


config = CourseAccessConfig()
