"""
App-level configuration for learner_management.

Provides a `config` object that resolves settings by checking Django's
``settings`` first, then falling back to the defaults declared here.

Usage::

    from freedom_ls.learner_management.config import config

    if count > config.BULK_BACKGROUND_THRESHOLD:
        # run the bulk action in a background task
"""

from __future__ import annotations

from freedom_ls.base.app_settings import AppSettings, Setting


class LearnerManagementConfig(AppSettings):
    BULK_BACKGROUND_THRESHOLD: int
    LEARNER_IMPORT_MAX_ROWS: int
    BULK_RECORD_RETENTION_DAYS: int

    declared_settings = {
        # A bulk action over more objects than this runs in a background task
        # instead of inside the request.
        "BULK_BACKGROUND_THRESHOLD": Setting(default=250),
        # The most data rows a learner import file may hold; a larger file is
        # rejected whole rather than truncated.
        "LEARNER_IMPORT_MAX_ROWS": Setting(default=2000),
        # How long a finished bulk run or learner import is kept before
        # housekeeping deletes it.
        "BULK_RECORD_RETENTION_DAYS": Setting(default=30),
    }


config = LearnerManagementConfig()
