from __future__ import annotations

from freedom_ls.base.app_settings import AppSettings, Setting


class FormEngineSettings(AppSettings):
    FORM_ENGINE_ANONYMOUS_UPLOAD_LIMIT: int
    FORM_ENGINE_ANONYMOUS_UPLOAD_WINDOW_SECONDS: int

    declared_settings = {
        # How many files one client may upload per window. 0 disables the cap.
        "FORM_ENGINE_ANONYMOUS_UPLOAD_LIMIT": Setting(default=30),
        "FORM_ENGINE_ANONYMOUS_UPLOAD_WINDOW_SECONDS": Setting(default=3600),
    }


config = FormEngineSettings()
