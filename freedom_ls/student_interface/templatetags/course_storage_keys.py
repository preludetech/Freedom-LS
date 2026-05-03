"""Single source of truth for the localStorage keys used by the student-
facing course UI.

The Alpine ``coursePart`` component reads / writes a per-course-part
expand/collapse flag in ``window.localStorage``. The key is derived from
the course slug and the course-part's index in the course's child list.

Anything that needs to address that key — the template that renders the
``data-storage-key`` attribute, and any test that asserts on the stored
value — must go through this module so the format lives in exactly one
place.
"""

from django import template

register = template.Library()

COURSE_PART_STORAGE_KEY_PREFIX = "coursePart"


def course_part_storage_key(course_slug: str, index: int) -> str:
    """Return the localStorage key for a course part's expand/collapse flag.

    ``index`` is the 1-based position of the course-part inside the course
    (matches Django's ``forloop.counter``).
    """
    return f"{COURSE_PART_STORAGE_KEY_PREFIX}_{course_slug}_{index}"


@register.simple_tag
def course_part_storage_key_tag(course_slug: str, index: int) -> str:
    """Template-tag wrapper around ``course_part_storage_key``.

    Usage:
        {% load course_storage_keys %}
        {% course_part_storage_key_tag course.slug forloop.counter %}
    """
    return course_part_storage_key(course_slug, index)
