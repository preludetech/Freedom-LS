"""Tests for the all_courses view and the dashboard view.

The dashboard view replaces the old ``partial_list_courses`` HTMX
endpoint; tests for that endpoint were deleted in the same change set.
"""

from __future__ import annotations

import re

import pytest

from django.test import Client
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.content_engine.models import Course
from freedom_ls.student_interface.utils import CourseListingStatus
from freedom_ls.student_management.factories import (
    RecommendedCourseFactory,
    UserCourseRegistrationFactory,
)
from freedom_ls.student_progress.factories import CourseProgressFactory


@pytest.fixture
def courses(mock_site_context) -> list[Course]:
    """Create three courses, each with a topic so progress can be calculated."""
    result = []
    for i, title in enumerate(["Course A", "Course B", "Course C"]):
        slug = title.lower().replace(" ", "-")
        course: Course = CourseFactory(title=title, slug=slug)
        topic = TopicFactory(title=f"Topic {i}", slug=f"topic-{i}", content="content")
        course.items.create(child=topic, order=0)
        result.append(course)
    return result


def _logged_in_client(user) -> Client:
    """Build a Client logged in as `user`. Local helper — do not lift across files."""
    client = Client()
    client.force_login(user)
    return client


# --- all_courses view ---


@pytest.mark.django_db
def test_all_courses_anonymous_redirects_to_login(client, courses, mock_site_context):
    """Anonymous users get bounced to login — same gate as the dashboard."""
    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 302
    assert "login" in response["Location"].lower()


@pytest.mark.django_db
def test_all_courses_started_course_has_progress_percentage(mock_site_context, courses):
    """Started courses in the all_courses view should have progress_percentage for progress bars."""
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=courses[0])
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200

    all_courses_list = list(response.context["all_courses"])
    started_course = next(c for c in all_courses_list if c.id == courses[0].id)
    # Real-value assertion: a freshly-registered course with no topic
    # completion has a progress percentage of 0. `hasattr` only proved the
    # attribute existed; this proves the annotation produced the right value.
    assert started_course.progress_percentage == 0


@pytest.mark.django_db
def test_all_courses_annotates_accent_slot_key(mock_site_context, courses):
    """Every course returned to the all_courses page has an ``accent_slot_key``."""
    user = UserFactory()
    client = _logged_in_client(user)
    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200
    from freedom_ls.content_engine.course_accent import PALETTE

    for course in response.context["all_courses"]:
        assert hasattr(course, "accent_slot_key")
        assert course.accent_slot_key in PALETTE


# --- dashboard view ---


@pytest.mark.django_db
def test_dashboard_authenticated_returns_200_with_user_label(
    mock_site_context, courses
):
    user = UserFactory(first_name="Ada")
    client = _logged_in_client(user)
    response = client.get(reverse("student_interface:dashboard"))
    assert response.status_code == 200
    # The greeting renders the user's first name.
    assert "Ada" in response.content.decode()


@pytest.mark.django_db
def test_dashboard_current_courses(mock_site_context, courses):
    """Registered non-completed courses appear under registered_courses."""
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=courses[0])
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:dashboard"))
    assert response.status_code == 200
    registered = response.context["registered_courses"]
    assert len(registered) == 1
    assert registered[0] == courses[0]
    assert courses[0].title in response.content.decode()


@pytest.mark.django_db
def test_dashboard_current_courses_have_progress_percentage(mock_site_context, courses):
    """In-progress courses show progress_percentage attribute for progress bars."""
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=courses[0])
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:dashboard"))
    registered = response.context["registered_courses"]
    assert len(registered) == 1
    assert hasattr(registered[0], "progress_percentage")


@pytest.mark.django_db
def test_dashboard_completed_courses(mock_site_context, courses):
    """Completed courses surface in completed_courses, not registered_courses."""
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=courses[0])
    CourseProgressFactory(user=user, course=courses[0], completed_time=timezone.now())
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:dashboard"))
    assert response.status_code == 200
    assert courses[0] in response.context["completed_courses"]
    assert courses[0] not in list(response.context["registered_courses"])
    assert courses[0].title in response.content.decode()


@pytest.mark.django_db
def test_dashboard_recommended_courses(mock_site_context, courses):
    """Recommended courses appear in recommended_courses context list."""
    user = UserFactory()
    RecommendedCourseFactory(user=user, collection=courses[0])
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:dashboard"))
    assert response.status_code == 200
    recommended = list(response.context["recommended_courses"])
    assert len(recommended) == 1
    assert recommended[0].collection == courses[0]
    assert courses[0].title in response.content.decode()


@pytest.mark.django_db
def test_dashboard_annotates_accent_on_every_course(mock_site_context, courses):
    """Every current/completed/recommended course gets an accent_slot_key."""
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=courses[0])
    UserCourseRegistrationFactory(user=user, collection=courses[1])
    CourseProgressFactory(user=user, course=courses[1], completed_time=timezone.now())
    RecommendedCourseFactory(user=user, collection=courses[2])
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:dashboard"))
    assert response.status_code == 200

    for course in response.context["registered_courses"]:
        assert hasattr(course, "accent_slot_key")
    for course in response.context["completed_courses"]:
        assert hasattr(course, "accent_slot_key")
    for rec in response.context["recommended_courses"]:
        assert hasattr(rec.collection, "accent_slot_key")


# --- dashboard available_courses ---


@pytest.mark.django_db
def test_dashboard_available_excludes_registered_and_completed(
    mock_site_context, courses
):
    """Available list omits both in-progress and completed registrations."""
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=courses[0])
    UserCourseRegistrationFactory(user=user, collection=courses[1])
    CourseProgressFactory(user=user, course=courses[1], completed_time=timezone.now())
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:dashboard"))
    assert response.status_code == 200
    available = response.context["available_courses"]
    assert courses[0] not in available
    assert courses[1] not in available


@pytest.mark.django_db
def test_dashboard_available_excludes_recommended(mock_site_context, courses):
    """Recommended courses do not also appear in the available list."""
    user = UserFactory()
    RecommendedCourseFactory(user=user, collection=courses[0])
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:dashboard"))
    assert response.status_code == 200
    available = response.context["available_courses"]
    assert courses[0] not in available


@pytest.mark.django_db
def test_dashboard_available_capped_at_three(mock_site_context, courses):
    """No more than three available courses are surfaced, even with more eligible."""
    user = UserFactory()
    CourseFactory(title="Course D", slug="course-d")
    CourseFactory(title="Course E", slug="course-e")
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:dashboard"))
    assert response.status_code == 200
    assert len(response.context["available_courses"]) == 3


@pytest.mark.django_db
def test_dashboard_available_includes_eligible_course(mock_site_context, courses):
    """A course with no registration or recommendation shows up as available."""
    user = UserFactory()
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:dashboard"))
    assert response.status_code == 200
    available = response.context["available_courses"]
    assert courses[0] in available


@pytest.mark.django_db
def test_dashboard_available_courses_have_preview_annotations(
    mock_site_context, courses
):
    """Available courses carry preview context with is_registered False."""
    user = UserFactory()
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:dashboard"))
    assert response.status_code == 200
    available = response.context["available_courses"]
    assert available
    for course in available:
        assert course.preview_is_registered is False
        assert course.preview_start_url


# --- dashboard "Available courses" section + Browse-all link ---


@pytest.mark.django_db
def test_dashboard_available_section_renders_browse_all_link(
    mock_site_context, courses
):
    """When eligible courses exist, the section shows a Browse-all-courses link."""
    user = UserFactory()
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:dashboard"))
    assert response.status_code == 200
    body = response.content.decode()

    assert "Available courses" in body
    assert "Browse all courses" in body
    # A real anchor pointing at the all-courses page.
    courses_url = reverse("student_interface:courses")
    assert f'href="{courses_url}"' in body


@pytest.mark.django_db
def test_dashboard_available_section_hidden_when_empty(mock_site_context, courses):
    """With no eligible courses, the whole section (heading + link) disappears."""
    user = UserFactory()
    # Register two and recommend the third -> nothing left to surface.
    UserCourseRegistrationFactory(user=user, collection=courses[0])
    UserCourseRegistrationFactory(user=user, collection=courses[1])
    RecommendedCourseFactory(user=user, collection=courses[2])
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:dashboard"))
    assert response.status_code == 200
    assert not response.context["available_courses"]
    body = response.content.decode()
    assert "Available courses" not in body
    assert "Browse all courses" not in body


@pytest.mark.django_db
def test_dashboard_old_all_courses_button_removed(mock_site_context, courses):
    """The old bottom 'All Courses' button no longer renders."""
    user = UserFactory()
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:dashboard"))
    assert response.status_code == 200
    assert "All Courses" not in response.content.decode()


@pytest.mark.django_db
def test_dashboard_empty_state_browse_courses_button_present(
    mock_site_context, courses
):
    """A learner with no registrations still sees the empty-state Browse button."""
    user = UserFactory()
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:dashboard"))
    assert response.status_code == 200
    body = response.content.decode()
    assert "You haven't signed up for any courses yet." in body
    assert "Browse courses" in body


@pytest.mark.django_db
def test_dashboard_completed_course_in_history_not_available(
    mock_site_context, courses
):
    """A completed course shows under Learning History, never under Available."""
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=courses[0])
    CourseProgressFactory(user=user, course=courses[0], completed_time=timezone.now())
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:dashboard"))
    assert response.status_code == 200
    assert courses[0] in response.context["completed_courses"]
    assert courses[0] not in response.context["available_courses"]
    body = response.content.decode()
    assert "Learning History" in body


# --- page <title> tags (Bug 2) ---


def _extract_title(body: str) -> str:
    """Pull the trimmed text inside the first <title>...</title> tag."""
    start = body.find("<title>")
    assert start != -1, "no opening <title> tag in response"
    end = body.find("</title>", start)
    assert end != -1, "no closing </title> tag in response"
    return body[start + len("<title>") : end].strip()


@pytest.mark.django_db
def test_dashboard_title_tag_says_dashboard(mock_site_context, courses):
    """The dashboard's browser-tab title is 'Dashboard'."""
    user = UserFactory()
    client = _logged_in_client(user)
    response = client.get(reverse("student_interface:dashboard"))
    assert response.status_code == 200
    assert _extract_title(response.content.decode()) == "Dashboard"


@pytest.mark.django_db
def test_all_courses_title_tag_says_all_courses(mock_site_context, courses):
    """The all-courses page's browser-tab title is 'All Courses'."""
    user = UserFactory()
    client = _logged_in_client(user)
    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200
    assert _extract_title(response.content.decode()) == "All Courses"


@pytest.mark.django_db
def test_course_preview_title_tag_uses_course_title(mock_site_context, courses):
    """The course-preview page's browser-tab title matches the course title."""
    user = UserFactory()
    client = _logged_in_client(user)
    response = client.get(
        reverse(
            "student_interface:course_preview", kwargs={"course_slug": courses[0].slug}
        )
    )
    assert response.status_code == 200
    assert _extract_title(response.content.decode()) == courses[0].title


# ---------------------------------------------------------------------------
# Task A2 — all_courses view: correct listing_status + progress_percentage
# ---------------------------------------------------------------------------
# NOTE: The row template (B4) that renders status-specific markup does not exist
# yet — it is added in Batch 3 (Task B4). The routing assertions below therefore
# verify the *context* attributes set on each course object rather than rendered
# HTML. Full row-markup routing tests will be added after B4.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_all_courses_not_registered_has_not_registered_status(
    mock_site_context, courses
):
    """An unregistered course has listing_status=NOT_REGISTERED on the context object."""
    user = UserFactory()
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200

    all_courses_list = list(response.context["all_courses"])
    course = next(c for c in all_courses_list if c.id == courses[0].id)
    assert course.listing_status == CourseListingStatus.NOT_REGISTERED
    assert course.progress_percentage == 0


@pytest.mark.django_db
def test_all_courses_not_registered_has_preview_context(mock_site_context, courses):
    """An unregistered course carries preview context (modal/deep-link affordance)."""
    user = UserFactory()
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200

    all_courses_list = list(response.context["all_courses"])
    course = next(c for c in all_courses_list if c.id == courses[0].id)
    # _annotate_preview_context sets preview_is_registered=False and preview_start_url
    assert course.preview_is_registered is False
    assert course.preview_start_url


@pytest.mark.django_db
def test_all_courses_registered_zero_percent_has_registered_status(
    mock_site_context, courses
):
    """A registered-but-not-started course has listing_status=REGISTERED and 0% progress."""
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=courses[0])
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200

    all_courses_list = list(response.context["all_courses"])
    course = next(c for c in all_courses_list if c.id == courses[0].id)
    assert course.listing_status == CourseListingStatus.REGISTERED
    assert course.progress_percentage == 0
    # NOTE (B4): when B4 row templates exist, assert aria-valuenow="0" in rendered HTML


@pytest.mark.django_db
def test_all_courses_in_progress_has_in_progress_status(mock_site_context, courses):
    """A started course has listing_status=IN_PROGRESS and progress_percentage > 0."""
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=courses[0])
    CourseProgressFactory(
        user=user, course=courses[0], progress_percentage=40, completed_time=None
    )
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200

    all_courses_list = list(response.context["all_courses"])
    course = next(c for c in all_courses_list if c.id == courses[0].id)
    assert course.listing_status == CourseListingStatus.IN_PROGRESS
    assert course.progress_percentage == 40
    # NOTE (B4): when B4 row templates exist, assert aria-valuenow > 0 in rendered HTML


@pytest.mark.django_db
def test_all_courses_complete_has_complete_status(mock_site_context, courses):
    """A completed course has listing_status=COMPLETE and no preview context."""
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=courses[0])
    CourseProgressFactory(
        user=user,
        course=courses[0],
        progress_percentage=100,
        completed_time=timezone.now(),
    )
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200

    all_courses_list = list(response.context["all_courses"])
    course = next(c for c in all_courses_list if c.id == courses[0].id)
    assert course.listing_status == CourseListingStatus.COMPLETE
    # Completed rows do not receive preview context — no _annotate_preview_context call
    assert not hasattr(course, "preview_is_registered")
    # NOTE (B4): when B4 row templates exist, assert link → course_finish URL in HTML


@pytest.mark.django_db
def test_all_courses_complete_course_not_annotated_with_annotate_next_up(
    mock_site_context, courses
):
    """Completed courses must not have next_up_* attributes (annotate_next_up removed)."""
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=courses[0])
    CourseProgressFactory(
        user=user,
        course=courses[0],
        progress_percentage=100,
        completed_time=timezone.now(),
    )
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:courses"))
    all_courses_list = list(response.context["all_courses"])
    course = next(c for c in all_courses_list if c.id == courses[0].id)
    assert not hasattr(course, "next_up_title")
    assert not hasattr(course, "next_up_url")


@pytest.mark.django_db
def test_all_courses_registered_course_not_annotated_with_annotate_next_up(
    mock_site_context, courses
):
    """Registered in-progress courses must not have next_up_* attributes (_annotate_next_up not called)."""
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=courses[0])
    CourseProgressFactory(
        user=user, course=courses[0], progress_percentage=30, completed_time=None
    )
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:courses"))
    all_courses_list = list(response.context["all_courses"])
    course = next(c for c in all_courses_list if c.id == courses[0].id)
    assert not hasattr(course, "next_up_title")
    assert not hasattr(course, "next_up_url")


@pytest.mark.django_db
def test_all_courses_renders_four_distinct_status_labels(mock_site_context, courses):
    """Each of the four registration states renders its own visible label, so a
    registered-but-unstarted course is no longer indistinguishable from an
    unregistered one. The old ambiguous "Not started" label is gone entirely."""
    user = UserFactory()
    # courses[0] -> Not registered (left unregistered)
    # courses[1] -> Registered (enrolled, 0% progress)
    UserCourseRegistrationFactory(user=user, collection=courses[1])
    # courses[2] -> In progress (enrolled, >0% progress)
    UserCourseRegistrationFactory(user=user, collection=courses[2])
    CourseProgressFactory(
        user=user, course=courses[2], progress_percentage=40, completed_time=None
    )
    # A fourth course -> Completed.
    completed = CourseFactory(title="Course D", slug="course-d")
    completed_topic = TopicFactory(title="Topic D", slug="topic-d", content="content")
    completed.items.create(child=completed_topic, order=0)
    UserCourseRegistrationFactory(user=user, collection=completed)
    CourseProgressFactory(
        user=user,
        course=completed,
        progress_percentage=100,
        completed_time=timezone.now(),
    )

    client = _logged_in_client(user)
    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200
    body = response.content.decode()

    assert "Not registered" in body
    assert "Registered" in body  # the registered-0% row (capital R, standalone)
    assert "In progress" in body
    assert "Completed" in body
    assert "Not started" not in body  # retired ambiguous label


# ---------------------------------------------------------------------------
# Task A3 — query-count regression tests (criterion 5)
# ---------------------------------------------------------------------------
# Both tests register ALL created courses so there are no unregistered rows.
# This isolates the batched status/progress path: the pre-existing preview
# children() walk (_annotate_preview_context) runs only for NOT_REGISTERED
# rows; keeping all rows registered means that path adds zero extra queries,
# allowing a clean constant-query assertion on the batched logic alone.
# The unregistered preview walk is pre-existing behaviour and out of scope
# for this task (spec A3 note).
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_all_courses_query_count_is_constant(
    mock_site_context, django_assert_num_queries
):
    """With N registered courses (mix of statuses), the query count is a small constant."""
    user = UserFactory()

    # Create 3 courses, each with a topic, covering all registered states.
    course_registered = CourseFactory(slug="qc-reg")
    topic_reg = TopicFactory(slug="topic-qc-reg", content="content")
    course_registered.items.create(child=topic_reg, order=0)
    UserCourseRegistrationFactory(user=user, collection=course_registered)

    course_in_progress = CourseFactory(slug="qc-ip")
    topic_ip = TopicFactory(slug="topic-qc-ip", content="content")
    course_in_progress.items.create(child=topic_ip, order=0)
    UserCourseRegistrationFactory(user=user, collection=course_in_progress)
    CourseProgressFactory(
        user=user,
        course=course_in_progress,
        progress_percentage=50,
        completed_time=None,
    )

    course_complete = CourseFactory(slug="qc-comp")
    topic_comp = TopicFactory(slug="topic-qc-comp", content="content")
    course_complete.items.create(child=topic_comp, order=0)
    UserCourseRegistrationFactory(user=user, collection=course_complete)
    CourseProgressFactory(
        user=user,
        course=course_complete,
        progress_percentage=100,
        completed_time=timezone.now(),
    )

    client = _logged_in_client(user)

    # Empirically determined constant — run once to observe, then locked here.
    # The count is small and fixed regardless of how many registered courses exist
    # (see companion test below). Update this number only if a deliberate schema
    # or middleware change is made.
    with django_assert_num_queries(10):
        response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_all_courses_query_count_does_not_grow_with_registrations(
    mock_site_context, django_assert_num_queries
):
    """With MORE registered courses the query count stays the same constant."""
    user = UserFactory()

    # Create 6 registered courses (double the baseline above) to prove the count
    # does not grow linearly with the number of registrations.
    for i in range(6):
        course = CourseFactory(slug=f"qc-scale-{i}")
        topic = TopicFactory(slug=f"topic-qc-scale-{i}", content="content")
        course.items.create(child=topic, order=0)
        UserCourseRegistrationFactory(user=user, collection=course)
        if i % 3 == 1:
            CourseProgressFactory(
                user=user, course=course, progress_percentage=30, completed_time=None
            )
        elif i % 3 == 2:
            CourseProgressFactory(
                user=user,
                course=course,
                progress_percentage=100,
                completed_time=timezone.now(),
            )

    client = _logged_in_client(user)

    # Same constant as test_all_courses_query_count_is_constant — proves O(1), not O(N).
    with django_assert_num_queries(10):
        response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Task B4 — row-markup routing tests (deferred from NOTE (B4) comments above)
# ---------------------------------------------------------------------------
# Now that the row templates exist (course_row_registered.html,
# course_row_complete.html, course_row_not_registered.html), these tests
# assert that the rendered HTML routes correctly: correct links, correct
# progress bar semantics, correct absence of progress bar where not wanted.
# No CSS / styling assertions — only functional semantics.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_all_courses_not_registered_row_has_preview_affordance(
    mock_site_context, courses
):
    """A not-registered course row renders a link to the course_preview URL (mobile path)."""
    user = UserFactory()
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200

    preview_url = reverse(
        "student_interface:course_preview",
        kwargs={"course_slug": courses[0].slug},
    )
    body = response.content.decode()
    assert preview_url in body


@pytest.mark.django_db
def test_all_courses_not_registered_row_has_no_progress_bar(mock_site_context, courses):
    """A not-registered course row does not render a progress bar."""
    user = UserFactory()
    # No registration — courses[0] is NOT_REGISTERED
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200

    body = response.content.decode()
    # The progress bar element is only present for registered/in-progress rows.
    # Locate the not-registered course section by its title and confirm no <progress>
    # appears in the page for the not-registered row.
    # (A simple check: if no courses are registered, NO progress bars exist.)
    assert "<progress" not in body


@pytest.mark.django_db
def test_all_courses_registered_zero_percent_row_links_to_first_item(
    mock_site_context, courses
):
    """A registered-0% row links to view_course_item at index=1."""
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=courses[0])
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200

    item_url = reverse(
        "student_interface:view_course_item",
        kwargs={"course_slug": courses[0].slug, "index": 1},
    )
    body = response.content.decode()
    assert item_url in body


@pytest.mark.django_db
def test_all_courses_registered_zero_percent_row_has_aria_valuenow_zero(
    mock_site_context, courses
):
    """A registered-0% row renders a progress bar with aria-valuenow='0'."""
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=courses[0])
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200

    body = response.content.decode()
    assert 'aria-valuenow="0"' in body


@pytest.mark.django_db
def test_all_courses_in_progress_row_links_to_first_item(mock_site_context, courses):
    """An in-progress row links to view_course_item at index=1."""
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=courses[0])
    CourseProgressFactory(
        user=user, course=courses[0], progress_percentage=55, completed_time=None
    )
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200

    item_url = reverse(
        "student_interface:view_course_item",
        kwargs={"course_slug": courses[0].slug, "index": 1},
    )
    body = response.content.decode()
    assert item_url in body


@pytest.mark.django_db
def test_all_courses_in_progress_row_has_aria_valuenow_above_zero(
    mock_site_context, courses
):
    """An in-progress row renders a progress bar with aria-valuenow > 0."""
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=courses[0])
    CourseProgressFactory(
        user=user, course=courses[0], progress_percentage=55, completed_time=None
    )
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200

    body = response.content.decode()
    assert 'aria-valuenow="55"' in body


@pytest.mark.django_db
def test_all_courses_complete_row_links_to_course_finish(mock_site_context, courses):
    """A completed-course row links to the course_finish URL."""
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=courses[0])
    CourseProgressFactory(
        user=user,
        course=courses[0],
        progress_percentage=100,
        completed_time=timezone.now(),
    )
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200

    finish_url = reverse(
        "student_interface:course_finish",
        kwargs={"course_slug": courses[0].slug},
    )
    body = response.content.decode()
    assert finish_url in body


@pytest.mark.django_db
def test_all_courses_complete_row_has_no_progress_bar(mock_site_context, courses):
    """A completed-course row does not render a progress bar."""
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=courses[0])
    CourseProgressFactory(
        user=user,
        course=courses[0],
        progress_percentage=100,
        completed_time=timezone.now(),
    )
    # Register and complete only courses[0]; courses[1] and [2] remain unregistered.
    # No registered-but-incomplete courses means no progress bars in the whole page.
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200

    body = response.content.decode()
    assert "<progress" not in body


@pytest.mark.django_db
def test_all_courses_status_icons_are_decorative(mock_site_context, courses):
    """Status icons are decorative: the icon backend always stamps the semantic
    slug as the svg's aria-label, so each status icon must be wrapped in an
    `aria-hidden="true"` element to keep that slug out of the accessibility tree.
    Status is conveyed by the adjacent visible text (WCAG 1.4.1), never the slug.
    """
    user = UserFactory()
    # In-progress and complete rows exercise the in_progress/complete icons.
    UserCourseRegistrationFactory(user=user, collection=courses[0])
    CourseProgressFactory(
        user=user, course=courses[0], progress_percentage=40, completed_time=None
    )
    UserCourseRegistrationFactory(user=user, collection=courses[1])
    CourseProgressFactory(
        user=user,
        course=courses[1],
        progress_percentage=100,
        completed_time=timezone.now(),
    )
    # courses[2] stays unregistered -> exercises the not_started icon.
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200

    body = response.content.decode()
    # Every status-icon svg (which carries aria-label="<slug>") must sit directly
    # inside an aria-hidden wrapper.
    for slug in ("in_progress", "not_started", "complete"):
        assert f'aria-label="{slug}"' in body, f"expected {slug} icon to render"
        assert re.search(
            rf'aria-hidden="true">\s*<svg[^>]*aria-label="{slug}"', body
        ), f"status icon {slug!r} is not wrapped in aria-hidden"
