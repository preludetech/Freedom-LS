from __future__ import annotations

from datetime import timedelta

from freedom_ls.base.app_settings import AppSettings, Setting


class DeadlinesConfig(AppSettings):
    DEADLINE_POLICY: str
    DEADLINE_POLICY_DEFAULTS: dict[str, object]

    declared_settings = {
        "DEADLINE_POLICY": Setting(
            default="freedom_ls.deadlines.policy.LayeredDeadlinePolicy"
        ),
        # The last layer: every key is always decided here, so "inherit" is not allowed.
        "DEADLINE_POLICY_DEFAULTS": Setting(
            default={
                "mark_overdue": True,
                "close_items": False,
                "end_course_access": False,
                "notify_educators": False,
                "grace_window": timedelta(0),
                "after_access_ended": "outline_and_results",
            }
        ),
    }


config = DeadlinesConfig()
