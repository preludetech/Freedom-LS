"""Single source of truth for the localStorage keys used by the learner-
facing course UI.

The Alpine ``coursePart`` component reads / writes a per-course-part
expand/collapse flag in ``window.localStorage``. The key is derived from
the course slug and the course part: its index in the course's child list for
the learning path, its slug for a scoped list such as the reference outline.

Anything that needs to address that key — the template that renders the
``data-storage-key`` attribute, and any test that asserts on the stored
value — must go through this module so the format lives in exactly one
place.
"""

from django import template

register = template.Library()

COURSE_PART_STORAGE_KEY_PREFIX = "coursePart"


def course_part_storage_key(
    course_slug: str, part_id: int | str, scope: str = ""
) -> str:
    """Return the localStorage key for a course part's expand/collapse flag.

    ``part_id`` names the course part within its list: its 1-based position
    (matches Django's ``forloop.counter``) in the learning path, or its slug in
    a scoped list, whose parts come and go as they gain and lose topics.
    ``scope`` names a list other than the learning path, such as the reference
    outline, so its parts do not share keys with the learning path's parts.
    """
    if scope:
        return f"{COURSE_PART_STORAGE_KEY_PREFIX}_{scope}_{course_slug}_{part_id}"
    return f"{COURSE_PART_STORAGE_KEY_PREFIX}_{course_slug}_{part_id}"


@register.simple_tag
def course_part_storage_key_tag(
    course_slug: str, part_id: int | str, scope: str = ""
) -> str:
    """Template-tag wrapper around ``course_part_storage_key``.

    Usage:
        {% load course_storage_keys %}
        {% course_part_storage_key_tag course.slug forloop.counter %}
        {% course_part_storage_key_tag course.slug part.slug "reference" %}
    """
    return course_part_storage_key(course_slug, part_id, scope)
