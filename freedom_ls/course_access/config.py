from __future__ import annotations

from freedom_ls.base.app_settings import AppSettings, Setting


class CourseAccessConfig(AppSettings):
    COURSE_ACCESS_BACKEND: str

    declared_settings = {
        "COURSE_ACCESS_BACKEND": Setting(required=True),
    }


config = CourseAccessConfig()
