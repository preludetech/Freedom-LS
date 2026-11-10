from __future__ import annotations

from freedom_ls.content_engine.models import Course


def course_details_context(course: Course) -> dict[str, object]:
    """What the course details surfaces show about a course, computed once
    so the learner page and the educator preview never disagree."""
    lesson_count = course.lesson_count()
    return {
        "lesson_count": lesson_count,
        "lesson_count_label": f"{lesson_count} lesson{'' if lesson_count == 1 else 's'}",
        "includes_assessments": course.includes_assessments(),
        "organisation": course.single_organisation(),
    }
