"""The shipped demo content has two same-titled organisation courses, one per
demo organisation, so the audience gate and the organisation byline can be
seen without anyone authoring content first.

Marked `fls_internal`: it reads `demo_content/`, which only this repo ships.
"""

from __future__ import annotations

import pytest

from freedom_ls.content_engine.models import Course, CourseAudience

pytestmark = pytest.mark.fls_internal


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("course_dir", "organisation_slug", "audience"),
    [
        (
            "functionality_demo_organisation_course_harbour",
            "harbour-college",
            CourseAudience.ORGANISATION_LEARNERS,
        ),
        (
            "functionality_demo_organisation_course_northwind",
            "northwind-logistics",
            CourseAudience.PUBLIC,
        ),
    ],
)
def test_each_demo_organisation_course_loads_with_its_organisation_and_audience(
    site,
    loaded_demo_content,
    mock_site_context,
    course_dir,
    organisation_slug,
    audience,
):
    course = Course.objects.get(site=site, file_path=f"{course_dir}/course.md")

    assert course.title == "Workplace Safety Essentials"
    assert list(course.organisations.values_list("slug", flat=True)) == [
        organisation_slug
    ]
    assert course.audience == audience
