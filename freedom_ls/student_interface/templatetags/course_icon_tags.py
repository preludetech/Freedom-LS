"""Template tag for rendering a course's icon.

Usage:

.. code-block:: django

    {% load course_icon_tags %}
    {% course_icon course.icon course.icon_fallback aria_label=course.title %}

The tag delegates to :func:`freedom_ls.student_interface.course_icon.render_course_icon`,
which encodes the resolution order. Templates never branch on icon-name shape.
"""

from __future__ import annotations

from django import template
from django.utils.safestring import SafeString

from freedom_ls.student_interface.course_icon import render_course_icon

register = template.Library()


@register.simple_tag
def course_icon(
    icon: str,
    icon_fallback: str = "",
    variant: str = "outline",
    css_class: str = "size-5",
    aria_label: str = "",
) -> SafeString:
    return render_course_icon(
        icon,
        icon_fallback,
        variant=variant,
        css_class=css_class,
        aria_label=aria_label,
    )
