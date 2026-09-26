"""URL builders for notification categories that target learner_interface objects.

Kept beside the URL each builder reverses, so freedom_ls.comms never needs to know
which app owns which route.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.urls import reverse

if TYPE_CHECKING:
    from freedom_ls.content_engine.models import Course


def course_home_url(course: Course) -> str:
    return reverse("learner_interface:course_home", kwargs={"course_slug": course.slug})
