"""The notification category registry: importable from settings without loading apps.

Mirrors freedom_ls/base/webhook_event_types.py so config/settings_base.py can build
NOTIFICATION_CATEGORIES before the app registry exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.utils.translation import gettext_lazy as _

if TYPE_CHECKING:
    from django_stubs_ext import StrPromise


@dataclass(frozen=True)
class NotificationCategory:
    key: str
    label: StrPromise
    icon: str
    message: StrPromise
    url_builder: str | None


FLS_NOTIFICATION_CATEGORIES: list[NotificationCategory] = [
    NotificationCategory(
        key="course.registered",
        label=_("Course registration"),
        icon="course",
        message=_("You're registered for %(course_title)s"),
        url_builder="freedom_ls.learner_interface.notification_urls.course_home_url",
    ),
    NotificationCategory(
        key="course.completed",
        label=_("Course completion"),
        icon="achievement",
        message=_("You completed %(course_title)s"),
        url_builder="freedom_ls.learner_interface.notification_urls.course_home_url",
    ),
]
