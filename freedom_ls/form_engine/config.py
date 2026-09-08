from __future__ import annotations

from freedom_ls.base.app_settings import AppSettings, Setting


class FormEngineConfig(AppSettings):
    # Dotted path to the scanner every uploaded answer file is handed to. FLS
    # ships an inert default, so a deployment that leaves it alone is warned by
    # system check W001.
    FILE_SCAN_BACKEND: str

    declared_settings = {
        "FILE_SCAN_BACKEND": Setting(
            default="freedom_ls.form_engine.scanning.NoOpScanner"
        ),
    }


config = FormEngineConfig()
