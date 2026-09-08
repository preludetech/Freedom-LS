"""A course names the form its applicants fill in as a path relative to its own
`course.md`. The schema is where that path is accepted; the loader resolves it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from freedom_ls.content_engine.schema import Course


def _course_data(**extra: object) -> dict[str, object]:
    return {
        "content_type": "COURSE",
        "file_path": "courses/data-science/course.md",
        "title": "Data science",
        **extra,
    }


def test_a_course_may_name_an_application_form():
    course = Course.model_validate(
        _course_data(application_form="../forms/application/form.md")
    )

    assert course.application_form == Path("../forms/application/form.md")


def test_a_course_need_not_name_an_application_form():
    course = Course.model_validate(_course_data())

    assert course.application_form is None


def test_an_unknown_key_is_still_refused():
    """`extra="forbid"` is what turns an author's typo into a load failure rather
    than a silently ignored line.
    """
    with pytest.raises(ValidationError):
        Course.model_validate(_course_data(aplication_form="../forms/form.md"))
