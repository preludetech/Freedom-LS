from typing import cast

import pytest

from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import (
    CourseCategoryFactory,
    CourseFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import Course, CourseCategory
from freedom_ls.learner_interface.tests.helpers import (
    rendered_section,
    section_by_slug,
)
from freedom_ls.learner_management.factories import LearnerCourseRegistrationFactory
from freedom_ls.learner_progress.tests.helpers import course_progress_record
from freedom_ls.tests.retire import retire

PLAYER_URL_NAMES = [
    ("view_course_item", {"index": 1}, "get"),
    ("form_start", {"index": 1}, "get"),
    ("form_fill_page", {"index": 1, "page_number": 1}, "get"),
    ("course_form_complete", {"index": 1}, "get"),
    ("form_submit_and_exit", {"index": 1}, "post"),
    ("course_finish", {}, "get"),
    ("course_reference", {}, "get"),
    (
        "course_reference_topic",
        {"part_slug": "a-part", "topic_slug": "a-topic"},
        "get",
    ),
]


def _course_with_topic(slug: str) -> Course:
    course: Course = CourseFactory(title=slug, slug=slug)
    course.items.create(child=TopicFactory(title=f"{slug} topic"), order=0)
    return course


@pytest.fixture
def live_and_retired(mock_site_context: object) -> tuple[Course, Course]:
    live = _course_with_topic("live-course")
    retired = retire(_course_with_topic("retired-course"))
    return live, retired


@pytest.fixture
def learner(live_and_retired: tuple[Course, Course]) -> tuple[Client, object]:
    user = UserFactory()
    for course in live_and_retired:
        LearnerCourseRegistrationFactory(learner__user=user, course=course)
    client = Client()
    client.force_login(user)
    return client, user


@pytest.mark.django_db
def test_catalogue_lists_a_live_course_and_not_a_retired_one(
    live_and_retired: tuple[Course, Course], learner: tuple[Client, object]
) -> None:
    client, _ = learner

    response = client.get(reverse("learner_interface:courses"))

    assert [c.slug for c in response.context["all_courses"]] == ["live-course"]


@pytest.mark.django_db
def test_catalogue_lists_no_retired_course_for_an_anonymous_visitor(
    live_and_retired: tuple[Course, Course],
) -> None:
    response = Client().get(reverse("learner_interface:courses"))

    assert [c.slug for c in response.context["all_courses"]] == ["live-course"]


@pytest.mark.django_db
def test_dashboard_discovery_lists_a_live_course_and_not_a_retired_one(
    live_and_retired: tuple[Course, Course],
) -> None:
    response = Client().get(reverse("learner_interface:dashboard"))

    assert [c.slug for c in rendered_section(response, "available").courses] == [
        "live-course"
    ]


@pytest.mark.django_db
def test_dashboard_in_progress_omits_a_retired_course(
    live_and_retired: tuple[Course, Course], learner: tuple[Client, object]
) -> None:
    client, _ = learner

    response = client.get(reverse("learner_interface:dashboard"))

    assert [c.slug for c in rendered_section(response, "in-progress").courses] == [
        "live-course"
    ]


@pytest.mark.django_db
def test_dashboard_history_omits_a_retired_completed_course(
    live_and_retired: tuple[Course, Course], learner: tuple[Client, object]
) -> None:
    client, user = learner
    live, retired = live_and_retired
    course_progress_record(live, user, completed_time=timezone.now())
    course_progress_record(retired, user, completed_time=timezone.now())

    response = client.get(reverse("learner_interface:dashboard"))

    assert [c.slug for c in rendered_section(response, "history").courses] == [
        "live-course"
    ]


@pytest.mark.django_db
@pytest.mark.parametrize("url_name", ["course_detail", "course_home"])
def test_course_page_is_404_for_a_registered_learner_of_a_retired_course(
    live_and_retired: tuple[Course, Course],
    learner: tuple[Client, object],
    url_name: str,
) -> None:
    client, _ = learner

    response = client.get(
        reverse(
            f"learner_interface:{url_name}", kwargs={"course_slug": "retired-course"}
        )
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_course_detail_is_404_for_an_anonymous_visitor_of_a_retired_course(
    live_and_retired: tuple[Course, Course],
) -> None:
    response = Client().get(
        reverse(
            "learner_interface:course_detail", kwargs={"course_slug": "retired-course"}
        )
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_initiate_course_access_is_404_for_a_retired_course(
    live_and_retired: tuple[Course, Course], learner: tuple[Client, object]
) -> None:
    client, _ = learner

    response = client.get(
        reverse(
            "learner_interface:initiate_course_access",
            kwargs={"course_slug": "retired-course"},
        )
    )

    assert response.status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize(("url_name", "kwargs", "method"), PLAYER_URL_NAMES)
def test_player_view_is_404_for_a_registered_learner_of_a_retired_course(
    live_and_retired: tuple[Course, Course],
    learner: tuple[Client, object],
    url_name: str,
    kwargs: dict[str, int | str],
    method: str,
) -> None:
    client, _ = learner
    url = reverse(
        f"learner_interface:{url_name}",
        kwargs={"course_slug": "retired-course", **kwargs},
    )

    response = getattr(client, method)(url)

    assert response.status_code == 404


@pytest.mark.django_db
@override_settings(OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE=True)
def test_visibility_override_does_not_reopen_a_retired_course(
    live_and_retired: tuple[Course, Course], learner: tuple[Client, object]
) -> None:
    client, _ = learner

    response = client.get(
        reverse(
            "learner_interface:course_detail", kwargs={"course_slug": "retired-course"}
        )
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_dashboard_category_sections_omit_a_retired_category(
    mock_site_context: object,
) -> None:
    live_category = CourseCategoryFactory(title="Live Cat", slug="live-cat")
    retired_category = retire(
        cast("CourseCategory", CourseCategoryFactory(title="Old Cat", slug="old-cat"))
    )
    CourseFactory(slug="in-live", dashboard_category=live_category)
    CourseFactory(slug="in-retired", dashboard_category=retired_category)

    response = Client().get(reverse("learner_interface:dashboard"))

    assert section_by_slug(response, "live-cat") is not None
    assert section_by_slug(response, "old-cat") is None


@pytest.mark.django_db
def test_live_course_under_a_retired_category_is_still_listed(
    mock_site_context: object,
) -> None:
    retired_category = retire(
        cast("CourseCategory", CourseCategoryFactory(title="Old Cat", slug="old-cat"))
    )
    CourseFactory(slug="in-retired", dashboard_category=retired_category)

    response = Client().get(reverse("learner_interface:dashboard"))

    assert [c.slug for c in rendered_section(response, "available").courses] == [
        "in-retired"
    ]


@pytest.mark.django_db
def test_course_detail_shows_no_chip_for_a_retired_dashboard_category(
    mock_site_context: object,
) -> None:
    retired_category = retire(
        cast("CourseCategory", CourseCategoryFactory(title="Old Cat", slug="old-cat"))
    )
    CourseFactory(slug="in-retired", dashboard_category=retired_category)

    response = Client().get(
        reverse("learner_interface:course_detail", kwargs={"course_slug": "in-retired"})
    )

    assert response.status_code == 200
    assert "course-category-chip" not in response.content.decode()
