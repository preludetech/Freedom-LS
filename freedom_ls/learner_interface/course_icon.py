"""Course-icon resolver.

This module lives in ``student_interface`` rather than in ``freedom_ls.icons``
so that the icons app stays portable and reusable in downstream Django
projects: "course icon resolution" is a student-interface concern.

The resolver walks the resolution order documented in the spec:

1. ``icon`` empty -> default semantic ``"course"``.
2. ``icon`` is a semantic name -> render via the icon backend.
3. ``icon`` is a literal glyph in the active icon set -> render that glyph.
4. ``icon_fallback`` (form ``<set>:<glyph>``) resolves -> render that glyph.
5. Otherwise -> render the default semantic ``"course"`` icon.
"""

from __future__ import annotations

from django.utils.safestring import SafeString

from freedom_ls.icons.render import IconResolutionError, render_icon

# Re-export so existing callers importing IconResolutionError from this module
# continue to work without change.
__all__ = ["IconResolutionError", "render_course_icon"]


def render_course_icon(
    icon: str,
    icon_fallback: str = "",
    *,
    variant: str = "outline",
    css_class: str = "size-5",
    aria_label: str = "",
) -> SafeString:
    """Render the icon for a course.

    See module docstring for the resolution order. Returns a
    :class:`~django.utils.safestring.SafeString` of the SVG markup.
    """
    return render_icon(
        icon,
        icon_fallback,
        default_semantic="course",
        variant=variant,
        css_class=css_class,
        aria_label=aria_label,
    )
