from __future__ import annotations

from freedom_ls.base.app_settings import AppSettings, Setting


class RevisionSettings(AppSettings):
    REVISION_SESSION_SIZE: int
    REVISION_DESIRED_RETENTION: float

    declared_settings = {
        "REVISION_SESSION_SIZE": Setting(default=15),
        "REVISION_DESIRED_RETENTION": Setting(default=0.9),
    }


config = RevisionSettings()
