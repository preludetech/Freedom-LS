"""
App-level configuration for student_management.

Provides a `config` object that resolves settings by checking Django's
``settings`` first, then falling back to the defaults declared here.

Usage::

    from freedom_ls.student_management.config import config

    if config.DEADLINES_ACTIVE:
        # show deadline UI
"""

from __future__ import annotations

from freedom_ls.base.app_settings import AppSettings, Setting


class StudentManagementConfig(AppSettings):
    DEADLINES_ACTIVE: bool

    declared_settings = {"DEADLINES_ACTIVE": Setting(default=True)}


config = StudentManagementConfig()
