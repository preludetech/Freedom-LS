from __future__ import annotations

from freedom_ls.base.app_settings import AppSettings, Setting


class CourseApplicationsSettings(AppSettings):
    COURSE_APPLICATIONS_ANONYMOUS_START_LIMIT: int
    COURSE_APPLICATIONS_ANONYMOUS_START_WINDOW_SECONDS: int

    declared_settings = {
        # How many applications one client may start per window. 0 disables the cap.
        "COURSE_APPLICATIONS_ANONYMOUS_START_LIMIT": Setting(default=10),
        "COURSE_APPLICATIONS_ANONYMOUS_START_WINDOW_SECONDS": Setting(default=3600),
    }


config = CourseApplicationsSettings()
