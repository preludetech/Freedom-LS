from __future__ import annotations

import io
import re
from datetime import timedelta

import lxml.html
import pytest
from PIL import Image

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import Client, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    CoursePartFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import Course, CoursePart, CourseVisibility, Topic
from freedom_ls.content_engine.tests.helpers import collection_item_for
from freedom_ls.course_access.backends import (
    CourseAccessDecision,
    FreeOnlyCourseAccessBackend,
)
from freedom_ls.course_access.loader import get_course_access_backend
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
    QuestionAnswerFactory,
    QuestionOptionFactory,
)
from freedom_ls.form_engine.models import (
    Form,
    FormProgress,
    FormStrategy,
    QuestionAnswer,
)
from freedom_ls.learner_interface.tests.helpers import (
    form_attempt,
    learner_with_two_grants,
    topic_completion,
)
from freedom_ls.learner_interface.utils import (
    BLOCKED,
    CourseListingStatus,
    current_entry_status,
    get_completed_courses,
    get_course_index,
    get_course_listing,
    get_current_courses,
    get_item_part,
    get_resume_index,
    outstanding_items,
)
from freedom_ls.learner_interface.views import _detail_cta_label
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortDeadlineFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
    LearnerDeadlineFactory,
)
from freedom_ls.learner_management.tests.helpers import register_user_for_course
from freedom_ls.learner_progress.attempts import get_or_create_incomplete
from freedom_ls.learner_progress.factories import (
    CourseFormAttemptFactory,
    CourseProgressFactory,
    TopicProgressFactory,
)
from freedom_ls.learner_progress.models import (
    CourseFormAttempt,
    CourseProgress,
    TopicProgress,
)
from freedom_ls.learner_progress.queries import course_progress_for
from freedom_ls.learner_progress.tests.helpers import course_progress_record
from freedom_ls.learner_progress.utils import ensure_course_progress_record
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.utils import get_default_organisation

# Tests for view_course_item with nested course structure.


@pytest.fixture
def course_with_nested_structure(mock_site_context, request):
    """
    Create a course with nested structure for testing flattened indices.

    Structure (URL indices in the viewable-only scheme):
      - CoursePart "Chapter 1" (no URL slot)
        - First content item (index 1)
        - Second content item (index 2)
      - Third content item (index 3, direct child of course)

    Can be parameterized with first_item_type to use Topic or Form.
    Returns dict with course and all content items.
    """
    first_item_type = getattr(request, "param", Topic)  # Default to Topic

    course: Course = CourseFactory(title="Test Course", slug="test-course")
    course_part: CoursePart = CoursePartFactory(title="Chapter 1", slug="chapter-1")

    if first_item_type == Topic:
        first_item = TopicFactory(
            title="First Topic",
            slug="first-topic",
            content="First item inside course part",
        )
    else:  # Form
        first_item = FormFactory(
            title="First Form",
            slug="first-form",
        )
        # Add a page to the form so it can be filled out
        FormPageFactory(
            form=first_item,
            title="Page 1",
            slug="page-1",
            order=0,
        )

    second_topic = TopicFactory(
        title="Second Topic",
        slug="second-topic",
        content="Second item inside course part",
    )

    third_topic = TopicFactory(
        title="Third Topic", slug="third-topic", content="Direct child of course"
    )

    # Build the structure
    course.items.create(child=course_part, order=0)
    course_part.items.create(child=first_item, order=0)
    course_part.items.create(child=second_topic, order=1)
    course.items.create(child=third_topic, order=1)

    return {
        "course": course,
        "course_part": course_part,
        "first_item": first_item,
        "second_item": second_topic,
        "third_item": third_topic,
    }


@pytest.fixture
def authenticated_client(mock_site_context, course_with_nested_structure):
    """Create an authenticated test client with a user registered for the test course."""
    user = UserFactory()
    LearnerCourseRegistrationFactory(
        learner__user=user, course=course_with_nested_structure["course"]
    )
    client = Client()
    client.force_login(user)
    return client


@pytest.mark.django_db
def test_accessing_topic_inside_course_part_should_display_topic(
    course_with_nested_structure, authenticated_client
):
    """
    Test that clicking on a topic inside a course part actually displays that topic.

    Regression test for bug where view_course_item used course.children() (non-flattened)
    with indices from get_course_index() (flattened), causing wrong items to be displayed.
    """
    first_topic = course_with_nested_structure["first_item"]

    # The first viewable item is at index 1 (CoursePart no longer consumes a slot)
    url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": "test-course", "index": 1},
    )

    response = authenticated_client.get(url)

    # Should display the correct topic, not redirect
    assert response.status_code == 200, (
        f"Should return 200, not redirect. Got {response.status_code}"
    )
    assert "topic" in response.context, "Should have topic in context"
    actual_topic = response.context["topic"]
    assert actual_topic == first_topic, (
        f"Should display 'First Topic', but got '{actual_topic.title}'"
    )
    # Template binding check: the topic title must show up in the rendered
    # page, not only in the context dict.
    assert first_topic.title in response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize("course_with_nested_structure", [Form], indirect=True)
def test_starting_form_inside_course_part_should_work(
    course_with_nested_structure, authenticated_client
):
    """
    Test that starting a form inside a course part works correctly.

    Ensures form_start view uses flattened indices like view_course_item.
    """
    first_form = course_with_nested_structure["first_item"]

    # The first viewable item is at index 1 (CoursePart no longer consumes a slot)
    url = reverse(
        "learner_interface:form_start",
        kwargs={"course_slug": "test-course", "index": 1},
    )

    response = authenticated_client.get(url, follow=True)

    # Should successfully handle the form
    assert response.status_code == 200
    assert "form" in response.context, "Should have form in context"
    actual_form = response.context["form"]
    assert actual_form == first_form, (
        f"Should work with 'First Form', but got '{actual_form.title}'"
    )
    # Template binding check.
    assert first_form.title in response.content.decode()


@pytest.mark.django_db
def test_view_course_item_anonymous_redirects_to_login(
    course_with_nested_structure, client
):
    """Anonymous user hitting view_course_item is redirected to login (login_required)."""
    # The first viewable item is at index 1 (CoursePart no longer consumes a slot)
    url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": "test-course", "index": 1},
    )
    response = client.get(url)
    assert response.status_code == 302
    assert "/login" in response.url


@pytest.mark.django_db
@pytest.mark.parametrize("course_with_nested_structure", [Form], indirect=True)
def test_form_start_anonymous_redirects_to_login(course_with_nested_structure, client):
    """Anonymous user hitting form_start is redirected to login (login_required)."""
    # The first viewable item is at index 1 (CoursePart no longer consumes a slot)
    url = reverse(
        "learner_interface:form_start",
        kwargs={"course_slug": "test-course", "index": 1},
    )
    response = client.get(url)
    assert response.status_code == 302
    assert "/login" in response.url


@pytest.mark.django_db
@pytest.mark.parametrize("course_with_nested_structure", [Form], indirect=True)
def test_form_complete_inside_course_part_should_work(
    course_with_nested_structure, authenticated_client
):
    """
    Test that viewing form completion page for a form inside a course part works.

    Ensures course_form_complete view uses flattened indices.
    """
    first_form = course_with_nested_structure["first_item"]

    # The first viewable item is at index 1 (CoursePart no longer consumes a slot)
    url = reverse(
        "learner_interface:course_form_complete",
        kwargs={"course_slug": "test-course", "index": 1},
    )

    response = authenticated_client.get(url)

    # Should successfully display the form complete page
    assert response.status_code == 200
    assert "form" in response.context, "Should have form in context"
    actual_form = response.context["form"]
    assert actual_form == first_form, (
        f"Should display completion for 'First Form', but got '{actual_form.title}'"
    )
    # Template binding check.
    assert first_form.title in response.content.decode()


@pytest.mark.django_db
def test_view_course_item_out_of_range_index_returns_404(
    course_with_nested_structure, authenticated_client
):
    """An index past the end of viewable_items returns 404, not 500."""
    course = course_with_nested_structure["course"]
    out_of_range = len(course.viewable_items()) + 1
    url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": "test-course", "index": out_of_range},
    )
    response = authenticated_client.get(url)
    assert response.status_code == 404


@pytest.mark.django_db
def test_view_course_item_zero_index_returns_404(
    course_with_nested_structure, authenticated_client
):
    """index=0 returns 404 instead of indexing into the last item."""
    url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": "test-course", "index": 0},
    )
    response = authenticated_client.get(url)
    assert response.status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize("course_with_nested_structure", [Form], indirect=True)
def test_form_start_out_of_range_index_returns_404(
    course_with_nested_structure, authenticated_client
):
    """form_start with an out-of-range index returns 404."""
    course = course_with_nested_structure["course"]
    out_of_range = len(course.viewable_items()) + 1
    url = reverse(
        "learner_interface:form_start",
        kwargs={"course_slug": "test-course", "index": out_of_range},
    )
    response = authenticated_client.get(url)
    assert response.status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize("course_with_nested_structure", [Form], indirect=True)
def test_course_form_complete_out_of_range_index_returns_404(
    course_with_nested_structure, authenticated_client
):
    """course_form_complete with an out-of-range index returns 404."""
    course = course_with_nested_structure["course"]
    out_of_range = len(course.viewable_items()) + 1
    url = reverse(
        "learner_interface:course_form_complete",
        kwargs={"course_slug": "test-course", "index": out_of_range},
    )
    response = authenticated_client.get(url)
    assert response.status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize("course_with_nested_structure", [Form], indirect=True)
def test_form_fill_page_out_of_range_index_returns_404(
    course_with_nested_structure, authenticated_client
):
    """form_fill_page with an out-of-range index returns 404."""
    course = course_with_nested_structure["course"]
    out_of_range = len(course.viewable_items()) + 1
    url = reverse(
        "learner_interface:form_fill_page",
        kwargs={
            "course_slug": "test-course",
            "index": out_of_range,
            "page_number": 1,
        },
    )
    response = authenticated_client.get(url)
    assert response.status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize("course_with_nested_structure", [Form], indirect=True)
def test_form_fill_page_out_of_range_page_returns_404(
    course_with_nested_structure, authenticated_client
):
    """form_fill_page with a valid index but out-of-range page_number returns 404."""
    url = reverse(
        "learner_interface:form_fill_page",
        kwargs={
            "course_slug": "test-course",
            "index": 1,
            "page_number": 999,
        },
    )
    response = authenticated_client.get(url)
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GA4 course_started event
#
# view_course_item both stamps started_at and renders the page in the same
# response, so the event shows up in that response's own HTML rather than
# surviving in the session for a later page to emit.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(GOOGLE_ANALYTICS_MEASUREMENT_ID="G-TEST")
def test_first_visit_to_a_course_emits_the_course_started_event(
    course_with_nested_structure, authenticated_client
):
    course = course_with_nested_structure["course"]
    url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": "test-course", "index": 1},
    )

    response = authenticated_client.get(url)

    assert (
        """gtag('event', 'course_started', {"course_slug": "test-course", """
        f'"course_id": "{course.id}", "access_type": "free", '
        '"registration_source": "individual"})'
    ) in response.content.decode()


@pytest.mark.django_db
@override_settings(GOOGLE_ANALYTICS_MEASUREMENT_ID="G-TEST")
def test_revisiting_the_course_does_not_emit_the_event_again(
    course_with_nested_structure, authenticated_client
):
    first_url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": "test-course", "index": 1},
    )
    second_url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": "test-course", "index": 2},
    )
    authenticated_client.get(first_url)

    response = authenticated_client.get(second_url)

    assert "gtag('event'" not in response.content.decode()


# Tests for prev/next navigation in view_course_item under the viewable-only index scheme.


@pytest.fixture
def course_starting_with_part(mock_site_context):
    """
    Course shape:
      - CoursePart "Chapter 1" (no URL slot)
        - Topic "First" (index 1)
        - Topic "Second" (index 2)
      - Topic "Third" (index 3, direct child of course)
    """
    course: Course = CourseFactory(title="Course", slug="course-a")
    part: CoursePart = CoursePartFactory(title="Chapter 1", slug="part-a")
    first = TopicFactory(title="First", slug="first", content="first")
    second = TopicFactory(title="Second", slug="second", content="second")
    third = TopicFactory(title="Third", slug="third", content="third")

    course.items.create(child=part, order=0)
    part.items.create(child=first, order=0)
    part.items.create(child=second, order=1)
    course.items.create(child=third, order=1)

    return {
        "course": course,
        "first": first,
        "second": second,
        "third": third,
    }


@pytest.fixture
def two_part_course(mock_site_context):
    """
    Course shape:
      - CoursePart "P1"
        - Topic "P1-A" (index 1)
        - Topic "P1-B" (index 2)
      - CoursePart "P2"
        - Topic "P2-A" (index 3)
        - Topic "P2-B" (index 4)
    """
    course: Course = CourseFactory(title="MultiPart", slug="multi-part")
    p1: CoursePart = CoursePartFactory(title="P1", slug="p1")
    p2: CoursePart = CoursePartFactory(title="P2", slug="p2")
    p1a = TopicFactory(title="P1-A", slug="p1-a", content="p1a")
    p1b = TopicFactory(title="P1-B", slug="p1-b", content="p1b")
    p2a = TopicFactory(title="P2-A", slug="p2-a", content="p2a")
    p2b = TopicFactory(title="P2-B", slug="p2-b", content="p2b")

    course.items.create(child=p1, order=0)
    course.items.create(child=p2, order=1)
    p1.items.create(child=p1a, order=0)
    p1.items.create(child=p1b, order=1)
    p2.items.create(child=p2a, order=0)
    p2.items.create(child=p2b, order=1)

    return {
        "course": course,
        "p1a": p1a,
        "p1b": p1b,
        "p2a": p2a,
        "p2b": p2b,
    }


@pytest.fixture
def authenticated_client_for(mock_site_context):
    """Factory fixture: authenticated client registered for the given course.

    Every topic is marked complete, which clears the sequential-unlock gate for
    the whole course: these tests exercise prev/next index arithmetic across
    part boundaries, and would otherwise be unable to open anything past item 1.
    """

    def _make(course: Course) -> Client:
        user = UserFactory()
        record = course_progress_record(course, user)
        for collection_item in course.viewable_collection_items():
            TopicProgress.objects.create(
                site_id=record.site_id,
                course_progress=record,
                collection_item=collection_item,
                topic=collection_item.child,
                complete_time=timezone.now(),
            )
        client = Client()
        client.force_login(user)
        return client

    return _make


@pytest.mark.django_db
def test_first_viewable_item_has_no_previous_url(
    course_starting_with_part, authenticated_client_for
):
    """At index=1 of a course that begins with a CoursePart, previous_url is None."""
    course = course_starting_with_part["course"]
    client = authenticated_client_for(course)

    url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    response = client.get(url)

    assert response.status_code == 200
    assert response.context["previous_url"] is None


@pytest.mark.django_db
def test_first_item_of_non_first_part_links_back_to_last_item_of_previous_part(
    two_part_course, authenticated_client_for
):
    """At index=3 (first item of P2), previous_url resolves to index=2 (last item of P1)."""
    course = two_part_course["course"]
    p1b = two_part_course["p1b"]
    client = authenticated_client_for(course)

    url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 3},
    )
    response = client.get(url)

    assert response.status_code == 200
    expected_prev = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 2},
    )
    assert response.context["previous_url"] == expected_prev

    # Following the previous URL should render P1-B with no redirect chain.
    prev_response = client.get(response.context["previous_url"])
    assert prev_response.status_code == 200
    assert prev_response.context["topic"] == p1b


@pytest.mark.django_db
def test_middle_of_part_prev_and_next_are_adjacent_viewables(
    two_part_course, authenticated_client_for
):
    """At index=2, previous_url ends with index=1 and next_url ends with index=3."""
    course = two_part_course["course"]
    client = authenticated_client_for(course)

    url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 2},
    )
    response = client.get(url)

    assert response.status_code == 200
    assert response.context["previous_url"] == reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    assert response.context["next_url"] == reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 3},
    )


@pytest.mark.django_db
def test_last_item_of_part_next_links_to_first_item_of_next_part(
    two_part_course, authenticated_client_for
):
    """At index=2 (last of P1), next_url is index=3 and renders P2-A directly (no redirect)."""
    course = two_part_course["course"]
    p2a = two_part_course["p2a"]
    client = authenticated_client_for(course)

    url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 2},
    )
    response = client.get(url)
    next_url = response.context["next_url"]

    expected_next = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 3},
    )
    assert next_url == expected_next

    # Direct GET on next_url renders P2-A with status 200 (no redirect plumbing).
    next_response = client.get(next_url)
    assert next_response.status_code == 200
    assert next_response.context["topic"] == p2a


@pytest.mark.django_db
def test_last_item_of_course_has_no_next_url(two_part_course, authenticated_client_for):
    """At index=4 (last viewable item), next_url is None."""
    course = two_part_course["course"]
    client = authenticated_client_for(course)

    url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 4},
    )
    response = client.get(url)

    assert response.status_code == 200
    assert response.context["next_url"] is None


@pytest.fixture
def topic_then_form_course(mock_site_context):
    """
    Course shape:
      - Topic "Intro" (index 1)
      - Form "Feedback" (index 2)
    """
    course: Course = CourseFactory(title="Topic then form", slug="topic-then-form")
    topic = TopicFactory(title="Intro", slug="intro", content="intro")
    form = FormFactory(title="Feedback", slug="feedback")

    ContentCollectionItemFactory(collection_object=course, child_object=topic, order=0)
    ContentCollectionItemFactory(collection_object=course, child_object=form, order=1)

    return {"course": course, "topic": topic, "form": form}


@pytest.fixture
def client_on_completed_form(topic_then_form_course):
    """A learner who has finished the intro topic and sat the form at index 2.

    The intro topic has to be completed or the sequential-unlock gate redirects
    the form away before the start page ever renders.
    """
    course = topic_then_form_course["course"]
    user = UserFactory()
    register_user_for_course(course, user)
    topic_completion(
        course, user, topic_then_form_course["topic"], complete_time=timezone.now()
    )
    form_attempt(
        course, user, topic_then_form_course["form"], completed_time=timezone.now()
    )

    client = Client()
    client.force_login(user)
    return client


@pytest.mark.django_db
def test_form_item_previous_url_points_at_the_preceding_item(
    topic_then_form_course, client_on_completed_form
):
    """The form start page gets the same previous_url a topic at index 2 would."""
    course = topic_then_form_course["course"]

    url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 2},
    )
    response = client_on_completed_form.get(url)

    assert response.status_code == 200
    assert response.context["previous_url"] == reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 1},
    )


@pytest.mark.django_db
def test_completed_form_start_page_renders_a_previous_button(
    topic_then_form_course, client_on_completed_form
):
    """The form footer offers the way back, as every topic footer does."""
    course = topic_then_form_course["course"]

    url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 2},
    )
    response = client_on_completed_form.get(url)

    assert 'data-testid="previous-button"' in response.content.decode()


@pytest.mark.django_db
def test_first_item_form_start_page_has_no_previous_button(mock_site_context):
    """A form at index 1 has nothing behind it, so the footer offers no way back."""
    form = FormFactory(title="Only item", slug="only-item")
    course: Course = CourseFactory(title="Form first", slug="form-first")
    ContentCollectionItemFactory(collection_object=course, child_object=form, order=0)
    user = UserFactory()
    register_user_for_course(course, user)

    client = Client()
    client.force_login(user)
    url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    response = client.get(url)

    assert response.status_code == 200
    assert 'data-testid="previous-button"' not in response.content.decode()


@pytest.mark.django_db
def test_form_completion_page_previous_url_points_at_the_preceding_item(
    topic_then_form_course, client_on_completed_form
):
    """Previous means the previous course item here too, not the form's own start page."""
    course = topic_then_form_course["course"]

    url = reverse(
        "learner_interface:course_form_complete",
        kwargs={"course_slug": course.slug, "index": 2},
    )
    response = client_on_completed_form.get(url)

    assert response.status_code == 200
    assert response.context["previous_url"] == reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    assert 'data-testid="previous-button"' in response.content.decode()


@pytest.mark.django_db
def test_form_completion_page_footer_is_boosted_like_the_rest_of_the_player(
    topic_then_form_course, client_on_completed_form
):
    """The completion page shares the player's footer, so it swaps rather than reloads."""
    course = topic_then_form_course["course"]

    url = reverse(
        "learner_interface:course_form_complete",
        kwargs={"course_slug": course.slug, "index": 2},
    )
    response = client_on_completed_form.get(url)

    assert 'hx-select-oob="#course-toc-region"' in response.content.decode()


@pytest.mark.django_db
def test_first_item_form_completion_page_has_no_previous_button(mock_site_context):
    """A form at index 1 has nothing behind it, so its completion page offers no way back."""
    form = FormFactory(title="Only item", slug="only-item-complete")
    course: Course = CourseFactory(title="Form first", slug="form-first-complete")
    ContentCollectionItemFactory(collection_object=course, child_object=form, order=0)
    user = UserFactory()
    register_user_for_course(course, user)
    form_attempt(course, user, form, completed_time=timezone.now())

    client = Client()
    client.force_login(user)
    url = reverse(
        "learner_interface:course_form_complete",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    response = client.get(url)

    assert response.status_code == 200
    assert response.context["previous_url"] is None
    assert 'data-testid="previous-button"' not in response.content.decode()


# Tests for the player breadcrumb trail's first crumb destination.


def _breadcrumb_nav(html: str) -> str:
    """Extract the breadcrumb <nav>...</nav> block from a rendered player page."""
    match = re.search(r'<nav aria-label="Breadcrumb">.*?</nav>', html, flags=re.DOTALL)
    assert match is not None, "breadcrumb <nav> not found in response"
    return match.group(0)


@pytest.mark.django_db
def test_first_crumb_links_to_course_detail_not_item_one(mock_site_context):
    course = CourseFactory(title="Breadcrumb Course", slug="breadcrumb-course")
    topic = TopicFactory(title="Only Topic", slug="only-topic", content="x")
    course.items.create(child=topic, order=0)
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course)

    client = Client()
    client.force_login(user)
    url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": "breadcrumb-course", "index": 1},
    )
    response = client.get(url)
    assert response.status_code == 200

    nav_html = _breadcrumb_nav(response.content.decode())

    course_detail_url = reverse(
        "learner_interface:course_detail", kwargs={"course_slug": "breadcrumb-course"}
    )
    item_one_url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": "breadcrumb-course", "index": 1},
    )

    assert f'href="{course_detail_url}"' in nav_html
    assert f'href="{item_one_url}"' not in nav_html


# Tests for the resume redirect, last-accessed recording, and player helpers.


@pytest.fixture
def course_structure(mock_site_context):
    """Course: part "Chapter 1" [topic A (1), topic B (2)] + top-level topic C (3)."""
    course = CourseFactory(title="Resume Course", slug="resume-course")
    part = CoursePartFactory(title="Chapter 1", slug="chapter-1")
    topic_a = TopicFactory(title="Topic A", slug="topic-a", content="A")
    topic_b = TopicFactory(title="Topic B", slug="topic-b", content="B")
    topic_c = TopicFactory(title="Topic C", slug="topic-c", content="C")
    course.items.create(child=part, order=0)
    part.items.create(child=topic_a, order=0)
    part.items.create(child=topic_b, order=1)
    course.items.create(child=topic_c, order=1)
    return {
        "course": course,
        "part": part,
        "topic_a": topic_a,
        "topic_b": topic_b,
        "topic_c": topic_c,
    }


@pytest.fixture
def enrolled_user(mock_site_context, course_structure):
    user = UserFactory()
    LearnerCourseRegistrationFactory(
        learner__user=user, course=course_structure["course"]
    )
    return user


def complete_topics(course, user, *topics):
    """Clear the sequential-unlock gate ahead of the item a test wants to open.

    These tests are about breadcrumbs, titles and resume bookkeeping, not about
    gating, so they open items further in than a learner with no progress could
    reach on their own.
    """
    for topic in topics:
        topic_completion(course, user, topic, complete_time=timezone.now())


# --- get_resume_index ---------------------------------------------------------


@pytest.mark.django_db
def test_resume_index_no_progress_returns_one(course_structure, enrolled_user):
    assert get_resume_index(enrolled_user, course_structure["course"]) == 1


@pytest.mark.django_db
def test_resume_index_null_item_returns_one(course_structure, enrolled_user):
    course_progress_record(course_structure["course"], enrolled_user)
    assert get_resume_index(enrolled_user, course_structure["course"]) == 1


@pytest.mark.django_db
def test_resume_index_maps_stored_item_to_its_index(course_structure, enrolled_user):
    cp = course_progress_record(course_structure["course"], enrolled_user)
    cp.last_accessed_item = collection_item_for(
        course_structure["course"], course_structure["topic_b"]
    )
    cp.save()
    # Topic B is the second viewable item.
    assert get_resume_index(enrolled_user, course_structure["course"]) == 2


@pytest.mark.django_db
def test_resume_index_stored_item_no_longer_viewable_falls_back(
    course_structure, enrolled_user
):
    cp = course_progress_record(course_structure["course"], enrolled_user)
    cp.last_accessed_item = collection_item_for(
        course_structure["course"], course_structure["topic_b"]
    )
    cp.save()
    # Remove topic B from the course; it is no longer viewable.
    course_structure["part"].items.filter(
        child_id=course_structure["topic_b"].pk
    ).delete()
    assert get_resume_index(enrolled_user, course_structure["course"]) == 1


# --- get_item_part ------------------------------------------------------------


@pytest.mark.django_db
def test_get_item_part_returns_containing_part(course_structure):
    part = get_item_part(course_structure["course"], course_structure["topic_a"])
    assert part == course_structure["part"]


@pytest.mark.django_db
def test_get_item_part_top_level_item_returns_none(course_structure):
    assert (
        get_item_part(course_structure["course"], course_structure["topic_c"]) is None
    )


# --- current-item marking in get_course_index ---------------------------------


@pytest.mark.django_db
def test_get_course_index_marks_current_item(course_structure, enrolled_user):
    children = get_course_index(
        user=enrolled_user,
        course=course_structure["course"],
        current_index=2,
        can_access_content=True,
    )
    part_dict = children[0]
    assert part_dict["contains_current"] is True
    # Topic B is the second child of the part and the current item.
    assert part_dict["children"][1]["is_current"] is True
    assert part_dict["children"][0]["is_current"] is False
    # Top-level topic C is index 3, not current.
    assert children[1]["is_current"] is False


@pytest.mark.django_db
def test_current_entry_status_reads_a_row_nested_inside_a_part(
    course_structure, enrolled_user
):
    """The player's gate reads its answer off this row, and items inside a part
    are one level further down than the loop's own iteration."""
    children = get_course_index(
        user=enrolled_user,
        course=course_structure["course"],
        current_index=2,
        can_access_content=True,
    )

    assert current_entry_status(children) == "BLOCKED"


@pytest.mark.django_db
def test_current_entry_status_is_none_when_no_row_is_current(
    course_structure, enrolled_user
):
    """Callers read None as "not blocked", so it must only arise with no current row."""
    children = get_course_index(
        user=enrolled_user,
        course=course_structure["course"],
        can_access_content=True,
    )

    assert current_entry_status(children) is None


# --- view_course_item records last-accessed item ------------------------------


@pytest.mark.django_db
def test_viewing_topic_records_last_accessed_item(course_structure, enrolled_user):
    client = Client()
    client.force_login(enrolled_user)
    complete_topics(
        course_structure["course"], enrolled_user, course_structure["topic_a"]
    )
    url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": "resume-course", "index": 2},
    )
    response = client.get(url)
    assert response.status_code == 200
    cp = course_progress_record(course_structure["course"], enrolled_user)
    assert cp.last_accessed_item == collection_item_for(
        course_structure["course"], course_structure["topic_b"]
    )


# --- course_home redirector ---------------------------------------------------


@pytest.mark.django_db
def test_course_home_enrolled_no_progress_redirects_to_item_one(
    course_structure, enrolled_user
):
    client = Client()
    client.force_login(enrolled_user)
    url = reverse(
        "learner_interface:course_home", kwargs={"course_slug": "resume-course"}
    )
    response = client.get(url)
    assert response.status_code == 302
    assert response.url == reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": "resume-course", "index": 1},
    )


@pytest.mark.django_db
def test_course_home_enrolled_with_progress_redirects_to_last_item(
    course_structure, enrolled_user
):
    cp = course_progress_record(course_structure["course"], enrolled_user)
    cp.last_accessed_item = collection_item_for(
        course_structure["course"], course_structure["topic_c"]
    )
    cp.save()
    client = Client()
    client.force_login(enrolled_user)
    url = reverse(
        "learner_interface:course_home", kwargs={"course_slug": "resume-course"}
    )
    response = client.get(url)
    assert response.status_code == 302
    assert response.url == reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": "resume-course", "index": 3},
    )


@pytest.mark.django_db
def test_course_home_unenrolled_redirects_to_detail(course_structure):
    user = UserFactory()
    client = Client()
    client.force_login(user)
    url = reverse(
        "learner_interface:course_home", kwargs={"course_slug": "resume-course"}
    )
    response = client.get(url)
    assert response.status_code == 302
    assert response.url == reverse(
        "learner_interface:course_detail", kwargs={"course_slug": "resume-course"}
    )


@pytest.mark.django_db
def test_course_home_anonymous_redirects_to_login(course_structure, client):
    url = reverse(
        "learner_interface:course_home", kwargs={"course_slug": "resume-course"}
    )
    response = client.get(url)
    assert response.status_code == 302
    assert "/login" in response.url


@pytest.mark.django_db
def test_course_home_never_renders_start_page(course_structure, enrolled_user):
    """The bare URL is always a 302, never a 200 HTML start page."""
    client = Client()
    client.force_login(enrolled_user)
    url = reverse(
        "learner_interface:course_home", kwargs={"course_slug": "resume-course"}
    )
    response = client.get(url)
    assert response.status_code == 302


# --- initiate_course_access lands in the player -------------------------------


# --- view_form GET does not mint a spurious FormProgress ---------------------


@pytest.mark.django_db
def test_viewing_form_does_not_create_form_progress(mock_site_context):
    """A bare GET of a form item must not fabricate an in-progress attempt.

    Resume is driven by CourseProgress.last_accessed_item, not FormProgress
    timestamps, so view_form must not touch FormProgress on GET.
    """
    course = CourseFactory(title="Form Course", slug="form-course")
    form = FormFactory(title="A Form", slug="a-form")
    FormPageFactory(form=form, title="Page 1", slug="page-1", order=0)
    course.items.create(child=form, order=0)
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course)

    client = Client()
    client.force_login(user)
    url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": "form-course", "index": 1},
    )
    response = client.get(url)
    assert response.status_code == 200
    assert not CourseFormAttempt.objects.filter(
        course_progress__learner__user=user,
        form_progress__form=form,
    ).exists()
    # But the form IS recorded as the resume target.
    cp = course_progress_record(course, user)
    assert cp.last_accessed_item == collection_item_for(course, form)


# --- breadcrumb + page title -------------------------------------------------


@pytest.mark.django_db
def test_breadcrumb_includes_part_when_item_in_part(course_structure, enrolled_user):
    client = Client()
    client.force_login(enrolled_user)
    # Item index 1 is Topic A, inside the "Chapter 1" part.
    url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": "resume-course", "index": 1},
    )
    response = client.get(url)
    html = response.content.decode()
    # The part title appears in the breadcrumb trail.
    assert "Chapter 1" in html
    # The current item is exposed as the current page (non-linked).
    assert 'aria-current="page"' in html
    assert response.context["current_part"] == course_structure["part"]


@pytest.mark.django_db
def test_breadcrumb_drops_part_when_item_top_level(course_structure, enrolled_user):
    client = Client()
    client.force_login(enrolled_user)
    complete_topics(
        course_structure["course"],
        enrolled_user,
        course_structure["topic_a"],
        course_structure["topic_b"],
    )
    # Item index 3 is Topic C, a top-level item with no part.
    url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": "resume-course", "index": 3},
    )
    response = client.get(url)
    assert response.context["current_part"] is None


@pytest.mark.django_db
def test_page_title_is_item_course_site(course_structure, enrolled_user):
    client = Client()
    client.force_login(enrolled_user)
    complete_topics(
        course_structure["course"],
        enrolled_user,
        course_structure["topic_a"],
        course_structure["topic_b"],
    )
    # Item index 3 (top-level, no part): "{item} — {course} — {site}".
    url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": "resume-course", "index": 3},
    )
    html = client.get(url).content.decode()
    assert "Topic C — Resume Course —" in html


@pytest.mark.django_db
def test_page_title_includes_part_when_present(course_structure, enrolled_user):
    client = Client()
    client.force_login(enrolled_user)
    # Item index 1 (Topic A inside Chapter 1): part sits between item and course.
    url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": "resume-course", "index": 1},
    )
    html = client.get(url).content.decode()
    assert "Topic A — Chapter 1 — Resume Course —" in html


@pytest.mark.django_db
def test_initiate_course_access_lands_on_item_url(course_structure):
    user = UserFactory()
    client = Client()
    client.force_login(user)
    url = reverse(
        "learner_interface:initiate_course_access",
        kwargs={"course_slug": "resume-course"},
    )
    response = client.get(url, follow=True)
    # Final landing URL is a concrete item URL, not a rendered start page.
    final_url, _status = response.redirect_chain[-1]
    assert final_url == reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": "resume-course", "index": 1},
    )


# --- query-count guard --------------------------------------------------------


@pytest.mark.django_db
def test_player_page_query_count_is_bounded(
    course_structure, enrolled_user, django_assert_max_num_queries
):
    """Pin the player page's query budget so regressions stay visible.

    The player chrome assembles the outline, breadcrumb part lookup, progress,
    and per-item status. The budget is independent of item count because the
    page (a) walks the course tree once -- ``Course.children`` /
    ``CoursePart.children`` memoize per instance, so the repeated chrome
    traversals share one resolution -- and (b) bulk-fetches all topic/form
    progress into maps via ``_fetch_player_progress_maps`` instead of one query
    per item. The ceiling is 46, well below what a reintroduced full traversal
    or a per-item progress N+1 would cost. See
    ``test_player_page_query_count_does_not_grow_with_items``, which runs the
    same budget over a course three times the size.

    46 is the cold number. Some of these queries are served from caches that
    outlive a single test -- the header asks whether this user may enter the
    educator interface, and Django caches content types for the process -- so
    the same page costs 43 once an earlier test has warmed them. The ceiling is
    the cold number rather than the warm one: a max that only holds on a warm cache
    fails whenever this test runs early. Both numbers are far enough below a
    per-item regression for either to catch one.
    """
    client = Client()
    client.force_login(enrolled_user)
    url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": "resume-course", "index": 1},
    )
    with django_assert_max_num_queries(46):
        response = client.get(url)
    assert response.status_code == 200


@pytest.fixture
def big_course(mock_site_context):
    """Course with a 10-topic part plus 3 top-level forms (13 viewable items).

    Used to prove the player's query budget does not grow per item: a per-item
    progress N+1 or a re-traversal would blow past the same ceiling the tiny
    4-item fixture lives under.
    """
    course = CourseFactory(title="Big Course", slug="big-course")
    part = CoursePartFactory(title="Big Chapter", slug="big-chapter")
    course.items.create(child=part, order=0)
    for n in range(10):
        topic = TopicFactory(title=f"BT {n}", slug=f"bt-{n}", content="x")
        part.items.create(child=topic, order=n)
    for n in range(3):
        form = FormFactory(title=f"BF {n}", slug=f"bf-{n}")
        course.items.create(child=form, order=n + 1)
    return course


@pytest.mark.django_db
def test_player_page_query_count_does_not_grow_with_items(
    big_course, django_assert_max_num_queries
):
    """Nine extra items cost no extra queries, not nine.

    This 13-item fixture and the 4-item one above cost exactly the same: the
    bulk per-item fetches (topic/form progress, deadlines) already scale with
    the course's structure, not with item count read at request time. Adding
    forms and seven more topics to the part moves the count by nothing at all.
    A per-item progress N+1 (or a per-caller re-traversal) would put it well
    above this ceiling instead.

    Shares the ceiling with the test above, cold number and all -- see its
    docstring for why the budget is the cold 46 rather than the warm 43.
    """
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=big_course)
    client = Client()
    client.force_login(user)
    url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": "big-course", "index": 1},
    )
    with django_assert_max_num_queries(46):
        response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_get_course_index_status_semantics_preserved(mock_site_context):
    """Bulk-fetched progress yields the same per-item statuses + next_status flow.

    Covers every status value and the next_status propagation (an untouched item
    after a READY one becomes BLOCKED; completed/failed/in-progress items are
    independent of next_status).
    """
    course = CourseFactory(title="Status Course", slug="status-course")
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course)
    now = timezone.now()

    topic_complete = TopicFactory(title="T complete", slug="t-complete", content="x")
    topic_ready = TopicFactory(title="T ready", slug="t-ready", content="x")
    topic_blocked = TopicFactory(title="T blocked", slug="t-blocked", content="x")
    topic_in_progress = TopicFactory(title="T wip", slug="t-wip", content="x")
    quiz_passed = FormFactory(
        title="Q passed",
        slug="q-passed",
        strategy=FormStrategy.QUIZ,
        quiz_pass_percentage=80,
    )
    quiz_failed = FormFactory(
        title="Q failed",
        slug="q-failed",
        strategy=FormStrategy.QUIZ,
        quiz_pass_percentage=80,
    )
    form_done = FormFactory(title="F done", slug="f-done")
    form_untouched = FormFactory(title="F untouched", slug="f-untouched")

    ordered = [
        topic_complete,
        topic_ready,
        topic_blocked,
        topic_in_progress,
        quiz_passed,
        quiz_failed,
        form_done,
        form_untouched,
    ]
    for order, item in enumerate(ordered):
        course.items.create(child=item, order=order)

    topic_completion(course, user, topic_complete, complete_time=now)
    topic_completion(course, user, topic_in_progress)
    form_attempt(
        course,
        user,
        quiz_passed,
        completed_time=now,
        scores={"score": 8, "max_score": 10},
    )
    form_attempt(
        course,
        user,
        quiz_failed,
        completed_time=now,
        scores={"score": 5, "max_score": 10},
    )
    form_attempt(course, user, form_done, completed_time=now)

    children = get_course_index(user=user, course=course, can_access_content=True)
    statuses = [c["status"] for c in children]
    assert statuses == [
        "COMPLETE",
        "READY",
        "BLOCKED",
        "IN_PROGRESS",
        "COMPLETE",
        "FAILED",
        "COMPLETE",
        "READY",
    ]


@pytest.mark.django_db
def test_checkbox_quiz_ticking_every_option_blocks_navigation_as_failed(
    mock_site_context,
):
    """Regression test for the exact-match scoring fix: a checkbox quiz answered by
    ticking every option used to score 100% and read COMPLETE; it must now read
    FAILED and block progression via `next_status`."""
    course = CourseFactory(title="Checkbox Course", slug="checkbox-course")
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course)

    quiz = FormFactory(
        title="Checkbox quiz",
        slug="checkbox-quiz",
        strategy=FormStrategy.QUIZ,
        quiz_pass_percentage=70,
    )
    topic_after = TopicFactory(
        title="After the quiz", slug="after-the-quiz", content="x"
    )
    course.items.create(child=quiz, order=0)
    course.items.create(child=topic_after, order=1)

    page = FormPageFactory(form=quiz, order=0)
    question = FormQuestionFactory(form_page=page, type="checkboxes", order=0)
    correct_1 = QuestionOptionFactory(question=question, correct=True, order=0)
    correct_2 = QuestionOptionFactory(question=question, correct=True, order=1)
    wrong_1 = QuestionOptionFactory(question=question, correct=False, order=2)
    wrong_2 = QuestionOptionFactory(question=question, correct=False, order=3)

    form_progress = form_attempt(course, user, quiz)
    answer = QuestionAnswerFactory(form_progress=form_progress, question=question)
    answer.selected_options.add(correct_1, correct_2, wrong_1, wrong_2)
    form_progress.complete()

    children = get_course_index(user=user, course=course, can_access_content=True)
    statuses = [c["status"] for c in children]
    assert statuses == ["FAILED", "BLOCKED"]


@pytest.mark.django_db
def test_children_memoized_second_call_issues_no_queries(course_structure):
    """Course.children() caches per instance: a warmed call hits the DB zero times."""
    course = course_structure["course"]
    first = course.children()
    with CaptureQueriesContext(connection) as ctx:
        second = course.children()
    assert len(ctx.captured_queries) == 0
    assert [type(c) for c in second] == [type(c) for c in first]


@pytest.mark.django_db
def test_get_course_index_unregistered_user_skips_progress_queries(mock_site_context):
    """An authenticated-but-unregistered user reads no progress rows (all BLOCKED)."""
    course = CourseFactory(title="Closed Course", slug="closed-course")
    topic = TopicFactory(title="Locked", slug="locked", content="x")
    form = FormFactory(title="Locked form", slug="locked-form")
    course.items.create(child=topic, order=0)
    course.items.create(child=form, order=1)
    user = UserFactory()  # not registered for the course

    with CaptureQueriesContext(connection) as ctx:
        children = get_course_index(user=user, course=course, can_access_content=False)

    assert [c["status"] for c in children] == ["BLOCKED", "BLOCKED"]
    sql = " ".join(q["sql"].lower() for q in ctx.captured_queries)
    assert "learner_progress_topicprogress" not in sql
    assert "form_engine_formprogress" not in sql


# The course player enforces sequential unlock server-side, not just in the TOC.
#
# The TOC has always drawn a locked item as unlinked text, but the item's own URL
# was unguarded: a learner who failed a gating quiz could type the address and get
# the content, and the visit recorded progress that flipped the entry out of
# "Locked" for good. These tests pin the URL to what the TOC shows.


GATED_COURSE_SLUG = "gated-course"


@pytest.fixture
def gated_course(mock_site_context) -> dict:
    """topic_intro (1) -> quiz (2, pass 80) -> topic_after (3) -> form_four (4)."""
    course = CourseFactory(title="Gated Course", slug=GATED_COURSE_SLUG)
    topic_intro = TopicFactory(title="Intro", slug="intro", content="intro")
    quiz = FormFactory(
        title="Gating quiz",
        slug="gating-quiz",
        strategy=FormStrategy.QUIZ,
        quiz_pass_percentage=80,
    )
    topic_after = TopicFactory(title="After", slug="after", content="after")
    form_four = FormFactory(
        title="Closing quiz",
        slug="closing-quiz",
        strategy=FormStrategy.QUIZ,
        quiz_pass_percentage=80,
    )
    course.items.create(child=topic_intro, order=0)
    course.items.create(child=quiz, order=1)
    course.items.create(child=topic_after, order=2)
    course.items.create(child=form_four, order=3)

    page = FormPageFactory(form=quiz, order=0)
    question = FormQuestionFactory(form_page=page, type="checkboxes", order=0)
    right = QuestionOptionFactory(question=question, correct=True, order=0)
    wrong = QuestionOptionFactory(question=question, correct=False, order=1)

    closing_page = FormPageFactory(form=form_four, order=0)
    closing_question = FormQuestionFactory(
        form_page=closing_page, type="checkboxes", order=0
    )
    QuestionOptionFactory(question=closing_question, correct=True, order=0)

    return {
        "course": course,
        "topic_intro": topic_intro,
        "quiz": quiz,
        "quiz_right_option": right,
        "quiz_wrong_option": wrong,
        "topic_after": topic_after,
        "form_four": form_four,
        "closing_page": closing_page,
        "closing_question": closing_question,
    }


@pytest.fixture
def gated_learner(mock_site_context, gated_course, client):
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=gated_course["course"])
    client.force_login(user)
    return user


def _complete_topic(course, user, topic: Topic) -> None:
    topic_completion(course, user, topic, complete_time=timezone.now())


def _sit_gating_quiz(user, gated_course: dict, *, correct: bool) -> None:
    """One completed sitting of the gating quiz, scored by the real marker."""
    option = gated_course["quiz_right_option" if correct else "quiz_wrong_option"]
    form_progress = form_attempt(gated_course["course"], user, gated_course["quiz"])
    answer = QuestionAnswerFactory(
        form_progress=form_progress, question=option.question
    )
    answer.selected_options.add(option)
    form_progress.complete()


def _gated_item_url(index: int) -> str:
    return reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": GATED_COURSE_SLUG, "index": index},
    )


# --- the reported bug ---------------------------------------------------------


@pytest.mark.django_db
def test_failed_gating_quiz_leaves_the_next_item_unreachable_by_url(
    gated_course, gated_learner, client
):
    # Arrange
    _complete_topic(gated_course["course"], gated_learner, gated_course["topic_intro"])
    _sit_gating_quiz(gated_learner, gated_course, correct=False)

    # Act
    response = client.get(_gated_item_url(3))

    # Assert
    assert response.url == reverse(
        "learner_interface:course_detail", kwargs={"course_slug": GATED_COURSE_SLUG}
    )


@pytest.mark.django_db
def test_a_refused_item_records_no_topic_progress(gated_course, gated_learner, client):
    """The visit used to create the row that flipped the TOC entry to In progress."""
    # Arrange
    _complete_topic(gated_course["course"], gated_learner, gated_course["topic_intro"])
    _sit_gating_quiz(gated_learner, gated_course, correct=False)

    # Act
    client.get(_gated_item_url(3))

    # Assert
    assert not TopicProgress.objects.filter(
        course_progress=course_progress_record(gated_course["course"], gated_learner),
        collection_item=collection_item_for(
            gated_course["course"], gated_course["topic_after"]
        ),
    ).exists()


@pytest.mark.django_db
def test_a_refused_item_does_not_become_the_resume_target(
    gated_course, gated_learner, client
):
    # Arrange
    _complete_topic(gated_course["course"], gated_learner, gated_course["topic_intro"])
    _sit_gating_quiz(gated_learner, gated_course, correct=False)
    client.get(_gated_item_url(2))

    # Act
    client.get(_gated_item_url(3))

    # Assert
    progress = course_progress_record(gated_course["course"], gated_learner)
    assert progress.last_accessed_item == collection_item_for(
        gated_course["course"], gated_course["quiz"]
    )


@pytest.mark.django_db
def test_passing_the_gating_quiz_makes_the_next_item_reachable(
    gated_course, gated_learner, client
):
    # Arrange
    _complete_topic(gated_course["course"], gated_learner, gated_course["topic_intro"])
    _sit_gating_quiz(gated_learner, gated_course, correct=True)

    # Act
    response = client.get(_gated_item_url(3))

    # Assert
    assert response.status_code == 200


# --- the guard must not over-block --------------------------------------------


@pytest.mark.django_db
def test_the_first_item_is_always_reachable(gated_course, gated_learner, client):
    """A learner with no progress at all still has somewhere to start."""
    # Act
    response = client.get(_gated_item_url(1))

    # Assert
    assert response.status_code == 200


@pytest.mark.django_db
def test_a_failed_quiz_item_stays_reachable_so_it_can_be_retried(
    gated_course, gated_learner, client
):
    # Arrange
    _complete_topic(gated_course["course"], gated_learner, gated_course["topic_intro"])
    _sit_gating_quiz(gated_learner, gated_course, correct=False)

    # Act
    response = client.get(_gated_item_url(2))

    # Assert
    assert response.status_code == 200


@pytest.mark.django_db
def test_work_already_completed_survives_a_later_failed_re_sit(
    gated_course, gated_learner, client
):
    """Failing a re-sit withholds what comes next; it does not revoke what is done."""
    # Arrange
    _complete_topic(gated_course["course"], gated_learner, gated_course["topic_intro"])
    _sit_gating_quiz(gated_learner, gated_course, correct=True)
    _complete_topic(gated_course["course"], gated_learner, gated_course["topic_after"])
    _sit_gating_quiz(gated_learner, gated_course, correct=False)

    # Act
    response = client.get(_gated_item_url(3))

    # Assert
    assert response.status_code == 200


@pytest.mark.django_db
def test_marking_a_topic_complete_unlocks_the_next_item(
    gated_course, gated_learner, client
):
    """The topic page's Next button is a mark-complete POST, so the ordinary way
    forward has to keep working."""
    # Arrange
    client.post(_gated_item_url(1), {"mark_complete": ""})

    # Act
    response = client.get(_gated_item_url(2))

    # Assert
    assert response.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("index", "expected_status"), [(1, 200), (2, 200), (3, 302), (4, 302)]
)
def test_url_reachability_matches_the_locked_state_in_the_index(
    gated_course, gated_learner, client, index, expected_status
):
    """The bug was a disagreement between the two, so the agreement is the fix."""
    # Arrange
    _complete_topic(gated_course["course"], gated_learner, gated_course["topic_intro"])
    _sit_gating_quiz(gated_learner, gated_course, correct=False)

    # Act
    response = client.get(_gated_item_url(index))

    # Assert
    assert response.status_code == expected_status


@pytest.mark.django_db
def test_resuming_to_a_now_locked_item_lands_on_the_course_detail_page(
    gated_course, gated_learner, client
):
    """A learner who roamed freely before the guard existed has a stale resume
    pointer, and must not be bounced between the redirector and the guard."""
    # Arrange
    _complete_topic(gated_course["course"], gated_learner, gated_course["topic_intro"])
    _sit_gating_quiz(gated_learner, gated_course, correct=False)
    stale_pointer = course_progress_record(gated_course["course"], gated_learner)
    stale_pointer.last_accessed_item = collection_item_for(
        gated_course["course"], gated_course["topic_after"]
    )
    stale_pointer.save(update_fields=["last_accessed_item"])

    # Act
    response = client.get(
        reverse(
            "learner_interface:course_home", kwargs={"course_slug": GATED_COURSE_SLUG}
        ),
        follow=True,
    )

    # Assert
    assert response.redirect_chain[-1][0] == reverse(
        "learner_interface:course_detail", kwargs={"course_slug": GATED_COURSE_SLUG}
    )


# --- the form runner ----------------------------------------------------------


@pytest.mark.django_db
def test_a_locked_form_cannot_be_started(gated_course, gated_learner, client):
    """form_start mints the attempt, so it is the door that flips a locked quiz
    to In progress."""
    # Arrange
    _complete_topic(gated_course["course"], gated_learner, gated_course["topic_intro"])
    _sit_gating_quiz(gated_learner, gated_course, correct=False)

    # Act
    client.get(
        reverse(
            "learner_interface:form_start",
            kwargs={"course_slug": GATED_COURSE_SLUG, "index": 4},
        )
    )

    # Assert
    assert not CourseFormAttempt.objects.filter(
        course_progress=course_progress_record(gated_course["course"], gated_learner),
        collection_item=collection_item_for(
            gated_course["course"], gated_course["form_four"]
        ),
    ).exists()


@pytest.mark.django_db
def test_a_locked_form_page_saves_no_answers(gated_course, gated_learner, client):
    # Arrange
    _complete_topic(gated_course["course"], gated_learner, gated_course["topic_intro"])
    _sit_gating_quiz(gated_learner, gated_course, correct=False)

    # Act
    client.post(
        reverse(
            "learner_interface:form_fill_page",
            kwargs={"course_slug": GATED_COURSE_SLUG, "index": 4, "page_number": 1},
        ),
        {f"question_{gated_course['closing_question'].id}": "1"},
    )

    # Assert
    assert not QuestionAnswer.objects.filter(
        question=gated_course["closing_question"]
    ).exists()


@pytest.mark.django_db
def test_the_results_of_a_failed_attempt_stay_readable(
    gated_course, gated_learner, client
):
    """A learner may always read the score of a sitting they actually made."""
    # Arrange
    _complete_topic(gated_course["course"], gated_learner, gated_course["topic_intro"])
    _sit_gating_quiz(gated_learner, gated_course, correct=False)

    # Act
    response = client.get(
        reverse(
            "learner_interface:course_form_complete",
            kwargs={"course_slug": GATED_COURSE_SLUG, "index": 2},
        )
    )

    # Assert
    assert response.status_code == 200


# --- the form runner enforces course access too --------------------------------


@pytest.fixture
def outsider(mock_site_context, gated_course, client):
    """Signed in, but never registered for the course."""
    user = UserFactory()
    client.force_login(user)
    return user


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("url_name", "kwargs"),
    [
        ("form_start", {"course_slug": GATED_COURSE_SLUG, "index": 2}),
        (
            "form_fill_page",
            {"course_slug": GATED_COURSE_SLUG, "index": 2, "page_number": 1},
        ),
        ("course_form_complete", {"course_slug": GATED_COURSE_SLUG, "index": 2}),
    ],
)
def test_an_unregistered_learner_is_turned_away_from_the_form_runner(
    gated_course, outsider, client, url_name, kwargs
):
    """The TOC hides these links, and until now the URLs were unguarded."""
    # Act
    response = client.get(reverse(f"learner_interface:{url_name}", kwargs=kwargs))

    # Assert
    assert response.url == reverse(
        "learner_interface:course_detail", kwargs={"course_slug": GATED_COURSE_SLUG}
    )


@pytest.mark.django_db
def test_an_unregistered_learner_cannot_submit_and_exit(gated_course, outsider, client):
    # Act
    response = client.post(
        reverse(
            "learner_interface:form_submit_and_exit",
            kwargs={"course_slug": GATED_COURSE_SLUG, "index": 2},
        )
    )

    # Assert
    assert response.url == reverse(
        "learner_interface:course_detail", kwargs={"course_slug": GATED_COURSE_SLUG}
    )


@pytest.mark.django_db
def test_an_unregistered_learner_starting_a_form_creates_no_attempt(
    gated_course, outsider, client
):
    # Act
    client.get(
        reverse(
            "learner_interface:form_start",
            kwargs={"course_slug": GATED_COURSE_SLUG, "index": 2},
        )
    )

    # Assert
    assert not CourseFormAttempt.objects.filter(
        form_progress__form=gated_course["quiz"],
        course_progress__learner__user=outsider,
    ).exists()


@pytest.mark.django_db
def test_an_unregistered_learner_is_404d_by_a_hidden_course(
    gated_course, outsider, client
):
    """Hidden courses must not leak their existence through a 302-vs-404 split."""
    # Arrange
    course = gated_course["course"]
    course.visibility = CourseVisibility.HIDDEN
    course.save()

    # Act
    response = client.get(
        reverse(
            "learner_interface:form_start",
            kwargs={"course_slug": GATED_COURSE_SLUG, "index": 2},
        )
    )

    # Assert
    assert response.status_code == 404


@pytest.mark.django_db
def test_a_registered_learner_still_reaches_the_form_runner(
    gated_course, gated_learner, client
):
    """The access gate must not turn away the learners it is there to admit."""
    # Arrange
    _complete_topic(gated_course["course"], gated_learner, gated_course["topic_intro"])

    # Act
    response = client.get(
        reverse(
            "learner_interface:form_start",
            kwargs={"course_slug": GATED_COURSE_SLUG, "index": 2},
        )
    )

    # Assert
    assert response.status_code == 302
    assert "fill_form" in response.url


# --- the same lock, one level down ---------------------------------------------

PARTED_COURSE_SLUG = "parted-course"


@pytest.fixture
def parted_course(mock_site_context) -> dict:
    """topic (1) -> quiz (2, pass 80) -> part "Core Concepts" [topic (3), topic (4)].

    The shape the second reproduction came from: the whole part reads Locked in
    the index, and the bug was that the items inside it stayed reachable by URL.
    """
    course = CourseFactory(title="Parted Course", slug=PARTED_COURSE_SLUG)
    topic_intro = TopicFactory(title="Opening", slug="opening", content="opening")
    quiz = FormFactory(
        title="Gating quiz",
        slug="parted-gating-quiz",
        strategy=FormStrategy.QUIZ,
        quiz_pass_percentage=80,
    )
    part = CoursePartFactory(title="Core Concepts", slug="core-concepts")
    inside_first = TopicFactory(title="2.1", slug="two-one", content="two one")
    inside_second = TopicFactory(title="2.2", slug="two-two", content="two two")

    course.items.create(child=topic_intro, order=0)
    course.items.create(child=quiz, order=1)
    course.items.create(child=part, order=2)
    part.items.create(child=inside_first, order=0)
    part.items.create(child=inside_second, order=1)

    page = FormPageFactory(form=quiz, order=0)
    question = FormQuestionFactory(form_page=page, type="checkboxes", order=0)
    right = QuestionOptionFactory(question=question, correct=True, order=0)
    wrong = QuestionOptionFactory(question=question, correct=False, order=1)

    return {
        "course": course,
        "topic_intro": topic_intro,
        "quiz": quiz,
        "quiz_right_option": right,
        "quiz_wrong_option": wrong,
        "inside_first": inside_first,
        "inside_second": inside_second,
    }


@pytest.fixture
def parted_learner(mock_site_context, parted_course, client):
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=parted_course["course"])
    client.force_login(user)
    return user


@pytest.mark.django_db
def test_an_item_inside_a_locked_part_is_unreachable_by_url(
    parted_course, parted_learner, client
):
    # Arrange
    _complete_topic(
        parted_course["course"], parted_learner, parted_course["topic_intro"]
    )
    _sit_gating_quiz(parted_learner, parted_course, correct=False)

    # Act
    response = client.get(
        reverse(
            "learner_interface:view_course_item",
            kwargs={"course_slug": PARTED_COURSE_SLUG, "index": 3},
        )
    )

    # Assert
    assert response.status_code == 302
    assert response.url == reverse(
        "learner_interface:course_detail",
        kwargs={"course_slug": PARTED_COURSE_SLUG},
    )
    assert not TopicProgress.objects.filter(
        course_progress=course_progress_record(parted_course["course"], parted_learner),
        collection_item=collection_item_for(
            parted_course["course"], parted_course["inside_first"]
        ),
    ).exists()


NEAR_MISS_COURSE_SLUG = "near-miss-course"


@pytest.fixture
def near_miss_course(mock_site_context, client) -> dict:
    """topic (1) -> quiz (2, pass 90) -> topic (3), with the quiz sat at 85%.

    A score that clears a fixed 80% threshold but not the quiz's own pass mark is
    what pulls the start page's buttons and the gate apart.
    """
    course = CourseFactory(title="Near Miss", slug=NEAR_MISS_COURSE_SLUG)
    topic_intro = TopicFactory(title="Opening", slug="near-opening", content="opening")
    quiz = FormFactory(
        title="Strict quiz",
        slug="strict-quiz",
        strategy=FormStrategy.QUIZ,
        quiz_pass_percentage=90,
    )
    topic_after = TopicFactory(title="Closing", slug="near-closing", content="closing")
    course.items.create(child=topic_intro, order=0)
    course.items.create(child=quiz, order=1)
    course.items.create(child=topic_after, order=2)

    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course)
    client.force_login(user)

    _complete_topic(course, user, topic_intro)
    form_attempt(
        course,
        user,
        quiz,
        completed_time=timezone.now(),
        scores={"score": 17, "max_score": 20},
    )

    return {"course": course, "quiz": quiz, "topic_after": topic_after, "user": user}


def _near_miss_item_url(index: int) -> str:
    return reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": NEAR_MISS_COURSE_SLUG, "index": index},
    )


@pytest.mark.django_db
def test_a_failed_quiz_start_page_offers_a_retry_and_no_way_forward(
    near_miss_course, client
):
    """The start page's buttons are drawn from the same verdict as the gate.

    The quiz's own page is where a learner lands after failing, so a Next button
    here would send them at an item the gate then turns them away from.
    """
    # Act
    response = client.get(_near_miss_item_url(2))

    # Assert
    content = response.content.decode()
    assert 'data-testid="try-again-button"' in content
    assert 'data-testid="next-button"' not in content
    assert f'href="{_near_miss_item_url(3)}"' not in content


@pytest.mark.django_db
def test_the_item_after_a_near_miss_quiz_is_locked(near_miss_course, client):
    """The gate's half of the same verdict, so the two are pinned together."""
    # Act
    response = client.get(_near_miss_item_url(3))

    # Assert
    assert response.status_code == 302
    assert response.url == reverse(
        "learner_interface:course_detail",
        kwargs={"course_slug": NEAR_MISS_COURSE_SLUG},
    )


@pytest.mark.django_db
def test_a_passed_quiz_start_page_leads_on_to_the_next_item(
    gated_course, gated_learner, client
):
    """The other half of the same verdict: an 80% pass mark met at 100% moves on."""
    # Arrange
    _complete_topic(gated_course["course"], gated_learner, gated_course["topic_intro"])
    _sit_gating_quiz(gated_learner, gated_course, correct=True)

    # Act
    response = client.get(_gated_item_url(2))

    # Assert
    content = response.content.decode()
    assert 'data-testid="next-button"' in content
    assert 'data-testid="try-again-button"' not in content


# The course outline and the stored percentage agree on what a placement's status is.
#
# Two read paths used to answer "is this form placement done" from different
# sittings: the outline read the latest *started* attempt, while the percentage and
# the finish page read the latest *completed* one. A learner who passed a quiz and
# then began a retry they never finished put an open attempt at the head of the
# outline's ordering, so the outline called the placement unfinished -- and, because
# the outline is what the player gates on, re-locked the rest of a course they had
# already unlocked -- while the percentage beside it still counted it done.


RETRY_COURSE_SLUG = "retry-course"


@pytest.fixture
def retry_course(mock_site_context) -> dict:
    """topic_intro (1) -> quiz (2, pass 80) -> topic_after (3)."""
    course = CourseFactory(title="Retry Course", slug=RETRY_COURSE_SLUG)
    topic_intro = TopicFactory(title="Intro", slug="retry-intro", content="intro")
    quiz = FormFactory(
        title="Retry quiz",
        slug="retry-quiz",
        strategy=FormStrategy.QUIZ,
        quiz_pass_percentage=80,
    )
    topic_after = TopicFactory(title="After", slug="retry-after", content="after")
    course.items.create(child=topic_intro, order=0)
    course.items.create(child=quiz, order=1)
    course.items.create(child=topic_after, order=2)

    page = FormPageFactory(form=quiz, order=0)
    question = FormQuestionFactory(form_page=page, type="checkboxes", order=0)
    right = QuestionOptionFactory(question=question, correct=True, order=0)
    wrong = QuestionOptionFactory(question=question, correct=False, order=1)

    return {
        "course": course,
        "topic_intro": topic_intro,
        "quiz": quiz,
        "right": right,
        "wrong": wrong,
        "topic_after": topic_after,
    }


@pytest.fixture
def retry_learner(mock_site_context, retry_course, client):
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=retry_course["course"])
    client.force_login(user)
    return user


def _sit_retry_quiz(user, retry_course: dict, *, correct: bool) -> None:
    """One completed sitting of the quiz, scored by the real marker."""
    option = retry_course["right" if correct else "wrong"]
    attempt = form_attempt(retry_course["course"], user, retry_course["quiz"])
    answer = QuestionAnswerFactory(form_progress=attempt, question=option.question)
    answer.selected_options.add(option)
    attempt.complete()


def _begin_retry(user, retry_course: dict) -> None:
    """A fresh sitting the learner walks away from without finishing."""
    form_attempt(retry_course["course"], user, retry_course["quiz"])


def _statuses(user, retry_course: dict) -> list[str]:
    return [
        child["status"]
        for child in get_course_index(
            user=user, course=retry_course["course"], can_access_content=True
        )
    ]


# --- the reported bug ---------------------------------------------------------


@pytest.mark.django_db
def test_an_abandoned_retry_leaves_a_passed_quiz_complete_in_the_outline(
    retry_course, retry_learner
):
    # Arrange
    topic_completion(
        retry_course["course"],
        retry_learner,
        retry_course["topic_intro"],
        complete_time=timezone.now(),
    )
    _sit_retry_quiz(retry_learner, retry_course, correct=True)

    # Act
    _begin_retry(retry_learner, retry_course)

    # Assert
    assert _statuses(retry_learner, retry_course) == ["COMPLETE", "COMPLETE", "READY"]


@pytest.mark.django_db
def test_an_abandoned_retry_does_not_relock_the_item_after_a_passed_quiz(
    retry_course, retry_learner, client
):
    """The outline is what the player gates on, so a re-lock is a real lockout."""
    # Arrange
    topic_completion(
        retry_course["course"],
        retry_learner,
        retry_course["topic_intro"],
        complete_time=timezone.now(),
    )
    _sit_retry_quiz(retry_learner, retry_course, correct=True)
    _begin_retry(retry_learner, retry_course)

    # Act
    response = client.get(
        reverse(
            "learner_interface:view_course_item",
            kwargs={"course_slug": RETRY_COURSE_SLUG, "index": 3},
        )
    )

    # Assert
    assert response.status_code == 200


@pytest.mark.django_db
def test_the_outline_and_the_finish_page_agree_about_a_passed_quiz(
    retry_course, retry_learner
):
    # Arrange
    topic_completion(
        retry_course["course"],
        retry_learner,
        retry_course["topic_intro"],
        complete_time=timezone.now(),
    )
    _sit_retry_quiz(retry_learner, retry_course, correct=True)
    _begin_retry(retry_learner, retry_course)
    record = course_progress_record(retry_course["course"], retry_learner)
    record.refresh_from_db()

    # Act
    still_to_do = outstanding_items(record, retry_course["course"])

    # Assert
    quiz_status = _statuses(retry_learner, retry_course)[1]
    assert quiz_status == "COMPLETE"
    assert [entry.content for entry in still_to_do] == [retry_course["topic_after"]]
    assert record.progress_percentage == 67


# --- the statuses this must not change ----------------------------------------


@pytest.mark.django_db
def test_a_first_sitting_still_in_flight_reads_in_progress(retry_course, retry_learner):
    # Arrange / Act
    _begin_retry(retry_learner, retry_course)

    # Assert
    assert _statuses(retry_learner, retry_course)[1:] == ["IN_PROGRESS", "BLOCKED"]


@pytest.mark.django_db
def test_a_failed_sitting_still_reads_failed(retry_course, retry_learner):
    # Arrange / Act
    _sit_retry_quiz(retry_learner, retry_course, correct=False)

    # Assert
    assert _statuses(retry_learner, retry_course)[1:] == ["FAILED", "BLOCKED"]


@pytest.mark.django_db
def test_a_retry_of_a_failed_quiz_still_reads_in_progress(retry_course, retry_learner):
    # Arrange
    _sit_retry_quiz(retry_learner, retry_course, correct=False)

    # Act
    _begin_retry(retry_learner, retry_course)

    # Assert
    assert _statuses(retry_learner, retry_course)[1:] == ["IN_PROGRESS", "BLOCKED"]


@pytest.mark.django_db
def test_a_pass_after_a_fail_still_reads_complete(retry_course, retry_learner):
    # Arrange
    _sit_retry_quiz(retry_learner, retry_course, correct=False)

    # Act
    _sit_retry_quiz(retry_learner, retry_course, correct=True)

    # Assert
    assert _statuses(retry_learner, retry_course)[1:] == ["COMPLETE", "READY"]


@pytest.mark.django_db
def test_an_abandoned_retry_of_a_form_with_no_pass_mark_still_reads_complete(
    mock_site_context,
):
    """A survey has no bar to clear, so finishing one is enough however often it is reopened."""
    # Arrange
    course = CourseFactory(title="Survey Course", slug="survey-course")
    survey = FormFactory(title="Survey", slug="survey", quiz_pass_percentage=None)
    topic_after = TopicFactory(title="After", slug="survey-after", content="after")
    course.items.create(child=survey, order=0)
    course.items.create(child=topic_after, order=1)
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course)
    form_attempt(course, user, survey, completed_time=timezone.now())

    # Act
    form_attempt(course, user, survey)

    # Assert
    children = get_course_index(user=user, course=course, can_access_content=True)
    assert [child["status"] for child in children] == ["COMPLETE", "READY"]


# A course is complete when every item in it is, so the finish page must not stamp
# a completion while any topic is unread or any quiz is unpassed -- one never sat as
# much as one sat and failed.


def _finish(client, user, course):
    client.force_login(user)
    return client.get(
        reverse("learner_interface:course_finish", kwargs={"course_slug": course.slug})
    )


@pytest.mark.django_db
def test_finish_page_does_not_complete_a_course_with_a_failed_quiz(
    mock_site_context, client, course_with_scored_quiz, sit_quiz
):
    """A learner who failed the course's quiz is not marked as having completed it."""
    user = UserFactory()
    course, form, question, _right, wrong = course_with_scored_quiz(
        slug="finish-failed"
    )
    progress: CourseProgress = CourseProgressFactory(
        learner__user=user, course=course, completed_time=None
    )
    sit_quiz(progress, form, question, wrong)

    _finish(client, user, course)

    progress.refresh_from_db()
    assert progress.completed_time is None


@pytest.mark.django_db
def test_finish_page_completes_a_course_once_the_quiz_is_passed(
    mock_site_context, client, course_with_scored_quiz, sit_quiz
):
    """Passing the retry lets the finish page record the completion."""
    user = UserFactory()
    course, form, question, right, wrong = course_with_scored_quiz(slug="finish-passed")
    progress: CourseProgress = CourseProgressFactory(
        learner__user=user, course=course, completed_time=None
    )
    sit_quiz(progress, form, question, wrong)
    sit_quiz(progress, form, question, right)

    _finish(client, user, course)

    progress.refresh_from_db()
    assert progress.completed_time is not None


@pytest.mark.django_db
def test_finish_page_still_renders_for_a_course_with_a_failed_quiz(
    mock_site_context, client, course_with_scored_quiz, sit_quiz
):
    """Withholding the completion must not take the page away from the learner."""
    user = UserFactory()
    course, form, question, _right, wrong = course_with_scored_quiz(
        slug="finish-renders"
    )
    progress: CourseProgress = CourseProgressFactory(
        learner__user=user, course=course, completed_time=None
    )
    sit_quiz(progress, form, question, wrong)

    response = _finish(client, user, course)

    assert response.status_code == 200


@pytest.mark.django_db
def test_finish_page_names_the_unpassed_quiz_and_links_to_its_retry(
    mock_site_context, client, course_with_scored_quiz, sit_quiz
):
    """A withheld completion has to say what is left, not congratulate the learner."""
    user = UserFactory()
    course, form, question, _right, wrong = course_with_scored_quiz(slug="finish-names")
    progress: CourseProgress = CourseProgressFactory(
        learner__user=user, course=course, completed_time=None
    )
    sit_quiz(progress, form, question, wrong)

    content = _finish(client, user, course).content.decode()

    assert "Congratulations" not in content
    assert "finish the item below" in content  # one item, so no "items"
    assert form.title in content
    assert "Retry quiz" in content
    assert (
        reverse(
            "learner_interface:form_start",
            kwargs={"course_slug": course.slug, "index": 1},
        )
        in content
    )


@pytest.mark.django_db
def test_finish_page_congratulates_once_the_quiz_is_passed(
    mock_site_context, client, course_with_scored_quiz, sit_quiz
):
    """Passing the retry earns the completion copy and the completion date."""
    user = UserFactory()
    course, form, question, right, wrong = course_with_scored_quiz(
        slug="finish-congratulates"
    )
    progress: CourseProgress = CourseProgressFactory(
        learner__user=user, course=course, completed_time=None
    )
    sit_quiz(progress, form, question, wrong)
    sit_quiz(progress, form, question, right)

    content = _finish(client, user, course).content.decode()

    assert "Congratulations" in content
    assert 'data-testid="outstanding-items"' not in content
    assert "Completed:" in content


@pytest.mark.django_db
def test_finish_page_does_not_complete_a_course_with_a_never_sat_quiz(
    mock_site_context, client, course_with_scored_quiz
):
    """A quiz the learner never opened withholds the completion as firmly as one they failed."""
    user = UserFactory()
    course, _form, _question, _right, _wrong = course_with_scored_quiz(
        slug="finish-never-sat"
    )
    progress: CourseProgress = CourseProgressFactory(
        learner__user=user, course=course, completed_time=None
    )

    _finish(client, user, course)

    progress.refresh_from_db()
    assert progress.completed_time is None


@pytest.mark.django_db
def test_finish_page_does_not_complete_a_course_with_an_unread_topic(
    mock_site_context, client
):
    """Completion counts every item, not only the quizzes."""
    user = UserFactory()
    course = CourseFactory(title="Unread", slug="finish-unread-topic")
    topic = TopicFactory(title="Key Ideas", slug="finish-key-ideas", content="x")
    course.items.create(child=topic, order=0)
    progress: CourseProgress = CourseProgressFactory(
        learner__user=user, course=course, completed_time=None
    )

    _finish(client, user, course)

    progress.refresh_from_db()
    assert progress.completed_time is None


@pytest.mark.django_db
def test_finish_page_names_a_never_sat_quiz_and_offers_to_start_it(
    mock_site_context, client, course_with_scored_quiz
):
    """A quiz never sat is offered as a start, not as a retry of nothing.

    It is offered through the read-only start screen rather than form_start,
    which mints an attempt on GET -- see the test below.
    """
    user = UserFactory()
    course, form, _question, _right, _wrong = course_with_scored_quiz(
        slug="finish-start-quiz"
    )
    CourseProgressFactory(learner__user=user, course=course, completed_time=None)

    content = _finish(client, user, course).content.decode()

    assert "Congratulations" not in content
    assert form.title in content
    assert "Start quiz" in content
    assert "Retry quiz" not in content
    assert (
        reverse(
            "learner_interface:view_course_item",
            kwargs={"course_slug": course.slug, "index": 1},
        )
        in content
    )


@pytest.mark.django_db
def test_the_offer_to_start_a_quiz_does_not_go_through_a_writing_view(
    mock_site_context, client, course_with_scored_quiz
):
    """Following the offer must not sit the quiz on the learner's behalf.

    form_start mints a FormProgress and a CourseFormAttempt on GET, so
    offering it for a quiz never sat would let merely following the link and
    backing out leave an empty attempt behind -- which a submit-on-exit form
    later finalises into a zero-score sitting the learner never took.
    """
    user = UserFactory()
    course, form, _question, _right, _wrong = course_with_scored_quiz(
        slug="finish-start-quiz-no-write"
    )
    CourseProgressFactory(learner__user=user, course=course, completed_time=None)

    response = _finish(client, user, course)
    offered = response.context["outstanding_items"][0].url
    client.get(offered)

    assert not FormProgress.objects.filter(form=form).exists()
    assert not CourseFormAttempt.objects.exists()


@pytest.mark.django_db
def test_finish_page_names_an_unread_topic_and_links_to_it(mock_site_context, client):
    """An outstanding topic is named and linked, the same as an outstanding quiz."""
    user = UserFactory()
    course = CourseFactory(title="Unread", slug="finish-names-topic")
    topic = TopicFactory(title="Going Deeper", slug="finish-going-deeper", content="x")
    course.items.create(child=topic, order=0)
    CourseProgressFactory(learner__user=user, course=course, completed_time=None)

    content = _finish(client, user, course).content.decode()

    assert "Congratulations" not in content
    assert topic.title in content
    assert (
        reverse(
            "learner_interface:view_course_item",
            kwargs={"course_slug": course.slug, "index": 1},
        )
        in content
    )


@pytest.mark.django_db
def test_finish_page_offers_to_start_an_unfinished_survey(mock_site_context, client):
    """A form with no pass mark is started, not retried and not "passed"."""
    from freedom_ls.learner_interface.tests.helpers import (
        course_with_single_question_form,
    )

    user = UserFactory()
    course = course_with_single_question_form("Survey", "finish-survey")
    CourseProgressFactory(learner__user=user, course=course, completed_time=None)

    content = _finish(client, user, course).content.decode()

    assert "Congratulations" not in content
    assert "Start form" in content
    assert "Start quiz" not in content


# The player's writes land in the resolved course progress record, and only there.
#
# A learner can hold two registrations for one course, and therefore two records.
# Everything the player writes -- the resume pointer, topic completions, form
# attempts -- has to land in the one the registration order resolves to, and must
# leave the other alone.


BACKEND_PATH = (
    "freedom_ls.learner_interface.tests.views.test_course_player"
    ".ContentWithoutRegistrationBackend"
)


class ContentWithoutRegistrationBackend(FreeOnlyCourseAccessBackend):
    """A downstream-shaped backend that opens content to everyone.

    Core FLS cannot produce a learner with content access and no registration --
    every ``can_access_content=True`` branch is gated on one -- so the read-only
    degradation can only be exercised through a backend like this.
    """

    def get_access(self, *, user, course) -> CourseAccessDecision:
        return CourseAccessDecision(
            cta_label=None,
            cta_url=None,
            can_self_register=False,
            can_access_content=True,
        )


def _item_url(course: Course, index: int) -> str:
    return reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": index},
    )


def _mark_complete(client, course: Course, index: int) -> None:
    """Complete the item at `index`, which is what unlocks the one after it."""
    client.post(_item_url(course, index), {"mark_complete": "1"})


def _course_with_titled_topics(*titles: str) -> Course:
    course: Course = CourseFactory()
    for order, title in enumerate(titles):
        topic = TopicFactory(title=title)
        ContentCollectionItemFactory(
            collection_object=course, child_object=topic, order=order
        )
    return course


# ---------------------------------------------------------------------------
# Degradation: content access without a registration
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_the_player_renders_for_a_learner_with_no_registration(
    mock_site_context, client
):
    """A backend may open content to an unregistered learner; the player must cope."""
    course = _course_with_titled_topics("Only Topic")
    user = UserFactory()
    client.force_login(user)

    with override_settings(COURSE_ACCESS_BACKEND=BACKEND_PATH):
        get_course_access_backend.cache_clear()
        response = client.get(_item_url(course, 1))

    assert response.status_code == 200


@pytest.mark.django_db
def test_no_progress_is_written_for_a_learner_with_no_registration(
    mock_site_context, client
):
    """Nothing grants the course, so nothing may be recorded against it."""
    course = _course_with_titled_topics("Only Topic")
    user = UserFactory()
    client.force_login(user)

    with override_settings(COURSE_ACCESS_BACKEND=BACKEND_PATH):
        get_course_access_backend.cache_clear()
        client.get(_item_url(course, 1))

    assert not CourseProgress.objects.exists()
    assert not TopicProgress.objects.exists()


@pytest.mark.django_db
def test_the_player_reports_that_progress_cannot_be_recorded(mock_site_context, client):
    """The templates hide the completion control off this flag."""
    course = _course_with_titled_topics("Only Topic")
    user = UserFactory()
    client.force_login(user)

    with override_settings(COURSE_ACCESS_BACKEND=BACKEND_PATH):
        get_course_access_backend.cache_clear()
        response = client.get(_item_url(course, 1))

    assert response.context["can_record_progress"] is False


@pytest.mark.django_db
def test_marking_complete_without_a_registration_is_a_404(mock_site_context, client):
    """There is nowhere to record the completion, so the POST must not succeed."""
    course = _course_with_titled_topics("Only Topic")
    user = UserFactory()
    client.force_login(user)

    with override_settings(COURSE_ACCESS_BACKEND=BACKEND_PATH):
        get_course_access_backend.cache_clear()
        response = client.post(_item_url(course, 1), {"mark_complete": "1"})

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_registered_learner_can_record_progress(mock_site_context, client):
    """The same flag is True on the ordinary path, so the control is offered."""
    course = _course_with_titled_topics("Only Topic")
    user = UserFactory()
    course_progress_record(course, user)
    client.force_login(user)

    response = client.get(_item_url(course, 1))

    assert response.context["can_record_progress"] is True


# ---------------------------------------------------------------------------
# The resume pointer and the started_at stamp
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_the_resume_pointer_records_the_collection_item(mock_site_context, client):
    """The pointer names a position in the course, not the content it resolves to."""
    course = _course_with_titled_topics("First", "Second")
    user = UserFactory()
    record = course_progress_record(course, user)
    client.force_login(user)
    _mark_complete(client, course, 1)

    client.get(_item_url(course, 2))

    record.refresh_from_db()
    assert record.last_accessed_item == course.viewable_collection_items()[1]


@pytest.mark.django_db
def test_a_topic_placed_twice_resumes_to_the_position_visited(
    mock_site_context, client
):
    """Two placements of one topic are two positions, and resume must tell them apart."""
    course: Course = CourseFactory()
    topic = TopicFactory(title="Repeated Topic")
    filler = TopicFactory(title="Filler")
    ContentCollectionItemFactory(collection_object=course, child_object=topic, order=0)
    ContentCollectionItemFactory(collection_object=course, child_object=filler, order=1)
    second_placement = ContentCollectionItemFactory(
        collection_object=course, child_object=topic, order=2
    )
    user = UserFactory()
    record = course_progress_record(course, user)
    client.force_login(user)
    _mark_complete(client, course, 1)
    _mark_complete(client, course, 2)

    client.get(_item_url(course, 3))

    record.refresh_from_db()
    assert record.last_accessed_item == second_placement


@pytest.mark.django_db
def test_started_at_is_stamped_on_first_content_access(mock_site_context, client):
    """Registration mints the record; opening the content is what starts it."""
    course = _course_with_titled_topics("Only Topic")
    user = UserFactory()
    record = course_progress_record(course, user)
    assert record.started_at is None
    client.force_login(user)

    client.get(_item_url(course, 1))

    record.refresh_from_db()
    assert record.started_at is not None


@pytest.mark.django_db
def test_started_at_is_not_re_stamped_on_a_later_visit(mock_site_context, client):
    """ "Started" is the first visit, so a second visit must leave it alone."""
    course = _course_with_titled_topics("First", "Second")
    user = UserFactory()
    record = course_progress_record(course, user)
    client.force_login(user)
    client.get(_item_url(course, 1))
    record.refresh_from_db()
    first_stamp = record.started_at

    client.get(_item_url(course, 2))

    record.refresh_from_db()
    assert record.started_at == first_stamp


@pytest.mark.django_db
def test_a_percentage_recalculation_does_not_bump_last_accessed_time(
    mock_site_context, client
):
    """last_accessed_time is the player's to write; a background write is not a visit."""
    course = _course_with_titled_topics("Only Topic")
    user = UserFactory()
    record = course_progress_record(course, user)
    client.force_login(user)
    client.get(_item_url(course, 1))
    record.refresh_from_db()
    visited_at = record.last_accessed_time

    record.progress_percentage = 50
    record.save(update_fields=["progress_percentage"])

    record.refresh_from_db()
    assert record.last_accessed_time == visited_at


# ---------------------------------------------------------------------------
# One learner, two grants
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_completing_an_item_moves_only_the_resolved_records_percentage(
    mock_site_context, client
):
    """The cohort registration wins, so only the cohort record's percentage moves."""
    course = _course_with_titled_topics("Only Topic")
    user, cohort_record, individual_record = learner_with_two_grants(course)
    client.force_login(user)

    client.post(_item_url(course, 1), {"mark_complete": "1"})

    cohort_record.refresh_from_db()
    individual_record.refresh_from_db()
    assert cohort_record.progress_percentage == 100
    assert individual_record.progress_percentage == 0


@pytest.mark.django_db
def test_the_unresolved_record_keeps_no_resume_pointer(mock_site_context, client):
    """The individual record is a separate pass; visiting the course is not its visit."""
    course = _course_with_titled_topics("Only Topic")
    user, _cohort_record, individual_record = learner_with_two_grants(course)
    client.force_login(user)

    client.post(_item_url(course, 1), {"mark_complete": "1"})

    individual_record.refresh_from_db()
    assert individual_record.last_accessed_item is None


@pytest.mark.django_db
def test_the_unresolved_record_is_never_started(mock_site_context, client):
    """started_at belongs to the pass the learner actually made."""
    course = _course_with_titled_topics("Only Topic")
    user, _cohort_record, individual_record = learner_with_two_grants(course)
    client.force_login(user)

    client.post(_item_url(course, 1), {"mark_complete": "1"})

    individual_record.refresh_from_db()
    assert individual_record.started_at is None


@pytest.mark.django_db
def test_the_completion_is_recorded_against_the_resolved_record(
    mock_site_context, client
):
    """One TopicProgress row, and it hangs off the cohort record."""
    course = _course_with_titled_topics("Only Topic")
    user, cohort_record, _individual_record = learner_with_two_grants(course)
    client.force_login(user)

    client.post(_item_url(course, 1), {"mark_complete": "1"})

    completions = TopicProgress.objects.filter(complete_time__isnull=False)
    assert [c.course_progress_id for c in completions] == [cohort_record.id]


@pytest.mark.django_db
def test_the_finish_page_mints_the_record_a_bare_registration_never_had(
    mock_site_context, client
):
    """Every player entry point self-heals, the finish page included.

    A registration made before course progress records existed has no record
    until the learner opens the course. Reaching the finish page directly --
    a bookmark, or the back button after the completion redirect -- has to
    mint it too, or the page 404s on a registration that plainly grants the
    course.
    """
    course = _course_with_titled_topics("Only Topic")
    user = UserFactory()
    register_user_for_course(course, user)
    CourseProgress.objects.all().delete()
    assert not CourseProgress.objects.exists()
    client.force_login(user)

    response = client.get(
        reverse("learner_interface:course_finish", kwargs={"course_slug": course.slug})
    )

    assert response.status_code == 200
    assert CourseProgress.objects.filter(learner__user=user, course=course).count() == 1


# ---------------------------------------------------------------------------
# One user, two organisations
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_finishing_the_course_in_one_organisation_leaves_the_others_completed_time_and_resume_pointer_untouched(
    mock_site_context, client
):
    """A person studying the same course through two organisations holds two
    Learner rows and therefore two records. Finishing under the registration
    order resolves to must not stamp completed_time or the resume pointer
    onto the other organisation's record -- each organisation's pass is its
    own."""
    course = _course_with_titled_topics("Only Topic")
    user = UserFactory()
    other_registration = LearnerCourseRegistrationFactory(
        learner__user=user,
        course=course,
        learner__organisation=OrganisationFactory(),
    )
    resolved_registration = LearnerCourseRegistrationFactory(
        learner__user=user,
        course=course,
        learner__organisation=OrganisationFactory(),
    )
    other_record = ensure_course_progress_record(
        other_registration.learner, course, other_registration
    )
    ensure_course_progress_record(
        resolved_registration.learner, course, resolved_registration
    )
    client.force_login(user)
    # Stamps last_accessed_item on whichever record the registration order
    # resolves to -- the more recently registered one, per learner_for_course.
    _mark_complete(client, course, 1)

    client.get(
        reverse("learner_interface:course_finish", kwargs={"course_slug": course.slug})
    )

    other_record.refresh_from_db()
    assert other_record.completed_time is None
    assert other_record.last_accessed_item is None


# ---------------------------------------------------------------------------
# Form attempts are scoped to the record and the placement
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_an_open_attempt_under_another_record_is_not_resumed(
    mock_site_context, client, course_with_scored_quiz
):
    """An attempt started under one registration must never be resumed under another."""
    course, form, _question, _right, _wrong = course_with_scored_quiz()
    user, cohort_record, individual_record = learner_with_two_grants(course)
    get_or_create_incomplete(individual_record, collection_item_for(course, form))
    client.force_login(user)

    client.get(
        reverse(
            "learner_interface:form_start",
            kwargs={"course_slug": course.slug, "index": 1},
        )
    )

    assert CourseFormAttempt.objects.filter(course_progress=cohort_record).count() == 1


@pytest.mark.django_db
def test_the_start_screen_ignores_an_attempt_under_another_record(
    mock_site_context, client, course_with_scored_quiz, sit_quiz
):
    """A sitting made under the other registration is not this record's history."""
    course, form, question, right, _wrong = course_with_scored_quiz()
    user, _cohort_record, individual_record = learner_with_two_grants(course)
    sit_quiz(individual_record, form, question, right)
    client.force_login(user)

    response = client.get(_item_url(course, 1))

    assert list(response.context["completed_form_progress"]) == []


@pytest.mark.django_db
def test_two_placements_of_one_form_keep_separate_attempts(
    mock_site_context, client, course_with_scored_quiz, sit_quiz
):
    """Answering a quiz at one position says nothing about the same quiz elsewhere."""
    course, form, question, right, _wrong = course_with_scored_quiz()
    user = UserFactory()
    record = course_progress_record(course, user)
    sit_quiz(record, form, question, right)
    ContentCollectionItemFactory(collection_object=course, child_object=form, order=1)
    client.force_login(user)

    response = client.get(_item_url(course, 2))

    assert list(response.context["completed_form_progress"]) == []


@pytest.mark.django_db
def test_a_completed_attempt_in_another_course_is_not_this_courses_history(
    mock_site_context, client, course_with_scored_quiz, sit_quiz
):
    """The same form placed in two courses is answered separately in each."""
    course, form, question, right, _wrong = course_with_scored_quiz()
    other_course: Course = CourseFactory()
    ContentCollectionItemFactory(
        collection_object=other_course, child_object=form, order=0
    )
    user = UserFactory()
    other_record = course_progress_record(other_course, user)
    course_progress_record(course, user)
    sit_quiz(other_record, form, question, right)
    client.force_login(user)

    response = client.get(_item_url(course, 1))

    assert list(response.context["completed_form_progress"]) == []


@pytest.mark.django_db
def test_a_deadline_lock_ignores_a_completion_in_another_course(
    mock_site_context, client, settings
):
    """A hard deadline locks the item here even though the topic is done elsewhere."""
    settings.DEADLINES_ACTIVE = True
    topic = TopicFactory(title="Shared Topic")
    course: Course = CourseFactory()
    other_course: Course = CourseFactory()
    ContentCollectionItemFactory(collection_object=course, child_object=topic, order=0)
    ContentCollectionItemFactory(
        collection_object=other_course, child_object=topic, order=0
    )
    user = UserFactory()
    record = course_progress_record(course, user)
    other_record = course_progress_record(other_course, user)
    TopicProgressFactory(
        course_progress=other_record,
        collection_item=collection_item_for(other_course, topic),
        topic=topic,
        complete_time=timezone.now(),
    )
    LearnerDeadlineFactory(
        learner_course_registration=record.learner_registration,
        content_item=topic,
        deadline=timezone.now() - timedelta(days=1),
        is_hard_deadline=True,
    )
    client.force_login(user)

    response = client.get(_item_url(course, 1))

    assert response.status_code == 302
    assert response["Location"] == reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )


# Every learner-facing figure is read off the resolved course progress record.
#
# These read paths fail silently: pointed at the wrong record they render a
# perfectly plausible page at a perfectly plausible percentage. So each test here
# asserts *whose* data reached the page, never that the page loaded.


def _course_with_slugged_topics(
    title: str, slug: str, count: int
) -> tuple[Course, list[Topic]]:
    course: Course = CourseFactory(title=title, slug=slug)
    topics: list[Topic] = []
    for n in range(count):
        topic: Topic = TopicFactory(
            title=f"{title} {n}", slug=f"{slug}-{n}", content="x"
        )
        course.items.create(child=topic, order=n)
        topics.append(topic)
    return course, topics


def _quiz(title: str, slug: str) -> Form:
    """A one-question quiz with a pass mark, so a wrong answer is a real fail."""
    quiz: Form = FormFactory(
        title=title,
        slug=slug,
        strategy=FormStrategy.QUIZ,
        quiz_pass_percentage=80,
    )
    page = FormPageFactory(form=quiz, order=0)
    question = FormQuestionFactory(form_page=page, type="multiple_choice", order=0)
    QuestionOptionFactory(question=question, text="Right", correct=True, order=0)
    QuestionOptionFactory(question=question, text="Wrong", correct=False, order=1)
    return quiz


# --- get_resume_index ---------------------------------------------------------


@pytest.mark.django_db
def test_resume_index_reads_the_resolved_records_pointer(mock_site_context):
    """Two records, two pointers: the cohort one is the one the learner resumes at."""
    course, topics = _course_with_slugged_topics("Resume", "resume-scoping", 3)
    user, cohort_record, individual_record = learner_with_two_grants(course)
    cohort_record.last_accessed_item = collection_item_for(course, topics[1])
    cohort_record.save(update_fields=["last_accessed_item"])
    individual_record.last_accessed_item = collection_item_for(course, topics[2])
    individual_record.save(update_fields=["last_accessed_item"])

    assert get_resume_index(user, course) == 2


# --- _fetch_player_progress_maps / get_content_status -------------------------


@pytest.mark.django_db
def test_a_topic_placed_twice_shows_independent_status_at_each_position(
    mock_site_context,
):
    """Completing the first placement must not complete the second.

    The progress maps key on the collection item; a topic-keyed map would read
    both positions as COMPLETE off the one completion.
    """
    course: Course = CourseFactory(title="Twice", slug="twice")
    topic = TopicFactory(title="Repeated", slug="repeated", content="x")
    course.items.create(child=topic, order=0)
    course.items.create(child=topic, order=1)
    user: User = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course)
    first_placement, _second_placement = course.viewable_collection_items()
    TopicProgressFactory(
        course_progress=course_progress_record(course, user),
        collection_item=first_placement,
        topic=topic,
        complete_time=timezone.now(),
    )

    children = get_course_index(user=user, course=course, can_access_content=True)

    assert [child["status"] for child in children] == ["COMPLETE", "READY"]


@pytest.mark.django_db
def test_a_topic_placed_twice_inside_a_part_shows_independent_status(
    mock_site_context,
):
    """The same, one level down -- the branch get_content_status recurses into."""
    course: Course = CourseFactory(title="Twice in a part", slug="twice-part")
    part = CoursePartFactory(title="Chapter", slug="twice-chapter")
    topic = TopicFactory(title="Repeated", slug="repeated-nested", content="x")
    course.items.create(child=part, order=0)
    part.items.create(child=topic, order=0)
    part.items.create(child=topic, order=1)
    user: User = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course)
    first_placement, _second_placement = course.viewable_collection_items()
    TopicProgressFactory(
        course_progress=course_progress_record(course, user),
        collection_item=first_placement,
        topic=topic,
        complete_time=timezone.now(),
    )

    children = get_course_index(user=user, course=course, can_access_content=True)

    assert [child["status"] for child in children[0]["children"]] == [
        "COMPLETE",
        "READY",
    ]


@pytest.mark.django_db
def test_the_outline_reads_the_resolved_records_completions(mock_site_context):
    """A completion recorded against the other record leaves the outline untouched."""
    course, topics = _course_with_slugged_topics("Outline", "outline-scoping", 2)
    user, _cohort_record, individual_record = learner_with_two_grants(course)
    TopicProgressFactory(
        course_progress=individual_record,
        collection_item=collection_item_for(course, topics[0]),
        topic=topics[0],
        complete_time=timezone.now(),
    )

    children = get_course_index(user=user, course=course, can_access_content=True)

    assert [child["status"] for child in children] == ["READY", "BLOCKED"]


# --- outstanding_items --------------------------------------------------------


@pytest.mark.django_db
def test_a_quiz_failed_in_another_course_does_not_withhold_this_completion(
    mock_site_context,
):
    """The same quiz can be placed in two courses; only this course's sitting counts."""
    quiz = _quiz("Shared quiz", "shared-quiz")
    this_course: Course = CourseFactory(title="This", slug="this-course")
    this_course.items.create(child=quiz, order=0)
    other_course: Course = CourseFactory(title="Other", slug="other-course")
    other_course.items.create(child=quiz, order=0)
    user: User = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=this_course)
    LearnerCourseRegistrationFactory(learner__user=user, course=other_course)

    form_attempt(
        other_course,
        user,
        quiz,
        completed_time=timezone.now(),
        scores={"score": 0, "max_score": 1},
    )
    form_attempt(
        this_course,
        user,
        quiz,
        completed_time=timezone.now(),
        scores={"score": 1, "max_score": 1},
    )

    record = course_progress_for(user, this_course)
    assert record is not None
    assert outstanding_items(record, this_course) == []


@pytest.mark.django_db
def test_a_fail_under_the_other_record_does_not_withhold_this_completion(
    mock_site_context,
):
    """One course, two records: only the resolved record's sittings are read."""
    course: Course = CourseFactory(title="Two grants quiz", slug="two-grants-quiz")
    quiz = _quiz("Gate", "gate-quiz")
    course.items.create(child=quiz, order=0)
    _user, cohort_record, individual_record = learner_with_two_grants(course)
    placement = collection_item_for(course, quiz)
    CourseFormAttemptFactory(
        course_progress=individual_record,
        collection_item=placement,
        form=quiz,
        form_progress__completed_time=timezone.now(),
        form_progress__scores={"score": 0, "max_score": 1},
    )
    CourseFormAttemptFactory(
        course_progress=cohort_record,
        collection_item=placement,
        form=quiz,
        form_progress__completed_time=timezone.now(),
        form_progress__scores={"score": 1, "max_score": 1},
    )

    assert outstanding_items(cohort_record, course) == []


@pytest.mark.django_db
def test_passing_one_placement_of_a_twice_placed_quiz_leaves_the_other_unpassed(
    mock_site_context,
):
    """Each placement is sat on its own, so a pass at one position cannot clear
    a fail at the other -- the learner still has that position to get right."""
    course: Course = CourseFactory(title="Twice", slug="twice-placed-quiz")
    quiz = _quiz("Repeated", "repeated-quiz")
    first_placement = course.items.create(child=quiz, order=0)
    second_placement = course.items.create(child=quiz, order=1)
    user: User = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course)
    record = course_progress_record(course, user)

    CourseFormAttemptFactory(
        course_progress=record,
        collection_item=second_placement,
        form=quiz,
        form_progress__completed_time=timezone.now(),
        form_progress__scores={"score": 0, "max_score": 1},
    )
    CourseFormAttemptFactory(
        course_progress=record,
        collection_item=first_placement,
        form=quiz,
        form_progress__completed_time=timezone.now(),
        form_progress__scores={"score": 1, "max_score": 1},
    )

    assert [entry.index for entry in outstanding_items(record, course)] == [2]


@pytest.mark.django_db
def test_a_never_sat_placement_of_a_twice_placed_quiz_is_outstanding(mock_site_context):
    """Passing one placement leaves the other to sit, not to skip.

    The completion this withholds is the one QA caught being stamped at 88%
    with the second placement still reading "Not started".
    """
    course: Course = CourseFactory(title="Twice unsat", slug="twice-placed-unsat")
    quiz = _quiz("Repeated unsat", "repeated-unsat-quiz")
    first_placement = course.items.create(child=quiz, order=0)
    course.items.create(child=quiz, order=1)
    user: User = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course)
    record = course_progress_record(course, user)

    CourseFormAttemptFactory(
        course_progress=record,
        collection_item=first_placement,
        form=quiz,
        form_progress__completed_time=timezone.now(),
        form_progress__scores={"score": 1, "max_score": 1},
    )

    assert [entry.index for entry in outstanding_items(record, course)] == [2]


@pytest.mark.django_db
def test_a_retry_is_only_offered_where_there_is_a_sitting_to_retry(mock_site_context):
    """The two kinds of outstanding quiz are told apart, so the page can word each one."""
    course: Course = CourseFactory(title="Retry flag", slug="retry-flag-course")
    failed = _quiz("Failed", "retry-flag-failed")
    untouched = _quiz("Untouched", "retry-flag-untouched")
    failed_placement = course.items.create(child=failed, order=0)
    course.items.create(child=untouched, order=1)
    user: User = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course)
    record = course_progress_record(course, user)

    CourseFormAttemptFactory(
        course_progress=record,
        collection_item=failed_placement,
        form=failed,
        form_progress__completed_time=timezone.now(),
        form_progress__scores={"score": 0, "max_score": 1},
    )

    assert [
        (entry.index, entry.is_retry) for entry in outstanding_items(record, course)
    ] == [
        (1, True),
        (2, False),
    ]


@pytest.mark.django_db
def test_an_unread_topic_is_outstanding_alongside_the_quizzes(mock_site_context):
    """A course is complete when every item is, so a topic withholds it too."""
    course: Course = CourseFactory(title="Mixed", slug="outstanding-mixed")
    topic: Topic = TopicFactory(
        title="Read me", slug="outstanding-read-me", content="x"
    )
    quiz = _quiz("Gate", "outstanding-gate")
    course.items.create(child=topic, order=0)
    quiz_placement = course.items.create(child=quiz, order=1)
    user: User = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course)
    record = course_progress_record(course, user)

    CourseFormAttemptFactory(
        course_progress=record,
        collection_item=quiz_placement,
        form=quiz,
        form_progress__completed_time=timezone.now(),
        form_progress__scores={"score": 1, "max_score": 1},
    )

    assert [entry.content for entry in outstanding_items(record, course)] == [topic]


# --- the three listings -------------------------------------------------------


@pytest.mark.django_db
def test_completed_courses_follow_the_resolved_record(mock_site_context):
    """A completion on the losing record must not mark the course finished."""
    course, _topics = _course_with_slugged_topics("Listing", "listing-completion", 1)
    user, _cohort_record, individual_record = learner_with_two_grants(course)
    individual_record.completed_time = timezone.now()
    individual_record.save(update_fields=["completed_time"])

    assert get_completed_courses(user) == []


@pytest.mark.django_db
def test_a_course_completed_on_the_resolved_record_is_listed_once(mock_site_context):
    """Two records for one course, one row in the history -- not two."""
    course, _topics = _course_with_slugged_topics("Listing", "listing-once", 1)
    user, cohort_record, _individual_record = learner_with_two_grants(course)
    cohort_record.completed_time = timezone.now()
    cohort_record.save(update_fields=["completed_time"])

    assert get_completed_courses(user) == [course]


@pytest.mark.django_db
def test_current_courses_show_the_resolved_records_percentage(mock_site_context):
    course, _topics = _course_with_slugged_topics("Listing", "listing-current", 1)
    user, cohort_record, individual_record = learner_with_two_grants(course)
    cohort_record.progress_percentage = 40
    cohort_record.save(update_fields=["progress_percentage"])
    individual_record.progress_percentage = 90
    individual_record.save(update_fields=["progress_percentage"])

    current = get_current_courses(user)

    assert [c.progress_percentage for c in current] == [40]


@pytest.mark.django_db
def test_a_course_completed_on_the_losing_record_stays_in_current_courses(
    mock_site_context,
):
    """Still in progress under the registration the learner is studying through."""
    course, _topics = _course_with_slugged_topics("Listing", "listing-still-current", 1)
    user, _cohort_record, individual_record = learner_with_two_grants(course)
    individual_record.completed_time = timezone.now()
    individual_record.save(update_fields=["completed_time"])

    assert get_current_courses(user) == [course]


@pytest.mark.django_db
def test_the_all_courses_listing_shows_the_resolved_records_percentage(
    mock_site_context,
):
    course, _topics = _course_with_slugged_topics("Listing", "listing-all-courses", 1)
    user, cohort_record, individual_record = learner_with_two_grants(course)
    cohort_record.progress_percentage = 25
    cohort_record.save(update_fields=["progress_percentage"])
    individual_record.progress_percentage = 100
    individual_record.completed_time = timezone.now()
    individual_record.save(update_fields=["progress_percentage", "completed_time"])

    entries = [entry for entry in get_course_listing(user) if entry.course == course]

    assert len(entries) == 1
    assert entries[0].progress_percentage == 25
    assert entries[0].status == CourseListingStatus.IN_PROGRESS


# --- _detail_cta_label --------------------------------------------------------


@pytest.mark.django_db
def test_a_registered_learner_who_never_opened_the_course_is_offered_start(
    mock_site_context,
):
    """The record exists from registration, so row-existence cannot mean "started"."""
    course, _topics = _course_with_slugged_topics("CTA", "cta-start", 1)
    user: User = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course)
    record = course_progress_record(course, user)

    assert record.progress_percentage == 0
    assert record.started_at is None
    assert _detail_cta_label(course, user) == "Start course"


@pytest.mark.django_db
def test_the_cta_reads_the_resolved_records_progress(mock_site_context):
    """Progress on the losing record must not turn Start into Continue."""
    course, _topics = _course_with_slugged_topics("CTA", "cta-continue", 1)
    user, _cohort_record, individual_record = learner_with_two_grants(course)
    individual_record.progress_percentage = 60
    individual_record.save(update_fields=["progress_percentage"])

    assert _detail_cta_label(course, user) == "Start course"


# --- the completion page's Started row ----------------------------------------


@pytest.mark.django_db
def test_course_finish_dates_the_start_from_content_access_not_registration(
    mock_site_context,
):
    """The registration is old; the learner began this month. The page says this month.

    ``created_at`` is the registration date, so binding the row to it would
    label the wrong day -- and Django resolves a wrong attribute name to the
    empty string rather than raising, so nothing else catches it.
    """
    course, _topics = _course_with_slugged_topics("Finish", "finish-started", 1)
    user: User = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course)
    record = course_progress_record(course, user)
    registered_at = timezone.now() - timezone.timedelta(days=400)
    CourseProgress.objects.filter(pk=record.pk).update(created_at=registered_at)
    began_at = timezone.now()
    record.started_at = began_at
    record.save(update_fields=["started_at"])

    client = Client()
    client.force_login(user)
    body = client.get(
        reverse("learner_interface:course_finish", kwargs={"course_slug": course.slug})
    ).content.decode()

    summary = re.sub(r"\s+", " ", body)
    assert f"Started:</span> <span>{began_at.strftime('%B %-d, %Y')}</span>" in summary
    assert registered_at.strftime("%B %-d, %Y") not in summary


@pytest.mark.django_db
def test_course_finish_omits_the_started_row_when_nothing_was_recorded(
    mock_site_context,
):
    """A null start renders no row at all, never a labelled blank."""
    course, _topics = _course_with_slugged_topics("Finish", "finish-no-start", 1)
    user: User = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course)
    record = course_progress_record(course, user)
    assert record.started_at is None

    client = Client()
    client.force_login(user)
    body = client.get(
        reverse("learner_interface:course_finish", kwargs={"course_slug": course.slug})
    ).content.decode()

    assert "Course Summary" in body
    assert "Started:" not in body


# --- the topic player's mark-complete button ----------------------------------


@pytest.mark.django_db
def test_a_learner_with_no_record_is_offered_no_mark_complete_button(
    mock_site_context, settings
):
    """Read-only degradation: nothing to write to, so no button that cannot work."""
    from freedom_ls.course_access.loader import get_course_access_backend

    course, _topics = _course_with_slugged_topics("Degraded", "degraded-topic", 2)
    user: User = UserFactory()  # never registered -- no record can be resolved
    settings.COURSE_ACCESS_BACKEND = (
        "freedom_ls.learner_interface.tests.views.test_course_player"
        ".ContentWithoutRegistrationBackend"
    )
    get_course_access_backend.cache_clear()

    client = Client()
    client.force_login(user)
    response = client.get(
        reverse(
            "learner_interface:view_course_item",
            kwargs={"course_slug": course.slug, "index": 1},
        )
    )
    get_course_access_backend.cache_clear()

    assert response.status_code == 200
    assert response.context["can_record_progress"] is False
    assert 'name="mark_complete"' not in response.content.decode()


@pytest.mark.django_db
def test_a_registered_learner_is_offered_the_mark_complete_button(mock_site_context):
    """The positive control -- otherwise the absence test above proves nothing."""
    course, _topics = _course_with_slugged_topics("Recorded", "recorded-topic", 2)
    user: User = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course)

    client = Client()
    client.force_login(user)
    response = client.get(
        reverse(
            "learner_interface:view_course_item",
            kwargs={"course_slug": course.slug, "index": 1},
        )
    )

    assert response.context["can_record_progress"] is True
    assert 'name="mark_complete"' in response.content.decode()


def _setup_cohort_registration(user, course):
    """Set up user in a cohort registered for a course. Returns the registration."""
    cohort = CohortFactory(name="Test Cohort")
    CohortMembershipFactory(learner__user=user, cohort=cohort)
    return CohortCourseRegistrationFactory(cohort=cohort, course=course)


@pytest.mark.django_db
@override_settings(DEADLINES_ACTIVE=True)
def test_course_index_includes_deadline_data(mock_site_context):
    """get_course_index includes deadline info in child dicts."""
    course: Course = CourseFactory(title="Test Course", slug="test-course")
    topic = TopicFactory(title="Test Topic", slug="test-topic")
    user = UserFactory()
    course.items.create(child=topic, order=0)

    registration = _setup_cohort_registration(user, course)
    deadline_dt = timezone.now() + timedelta(days=7)

    CohortDeadlineFactory(
        cohort_course_registration=registration,
        content_item=topic,
        deadline=deadline_dt,
    )

    children = get_course_index(user=user, course=course, can_access_content=True)

    assert len(children) == 1
    assert "deadlines" in children[0]
    assert len(children[0]["deadlines"]) == 1
    assert children[0]["deadlines"][0]["deadline"] == deadline_dt


@pytest.mark.django_db
@override_settings(DEADLINES_ACTIVE=True)
def test_expired_hard_deadline_locks_incomplete_item(mock_site_context):
    """Expired hard deadline + incomplete item = BLOCKED with no URL."""
    course: Course = CourseFactory(title="Test Course", slug="test-course")
    topic = TopicFactory(title="Test Topic", slug="test-topic")
    user = UserFactory()
    course.items.create(child=topic, order=0)

    registration = _setup_cohort_registration(user, course)

    CohortDeadlineFactory(
        cohort_course_registration=registration,
        content_item=topic,
        deadline=timezone.now() - timedelta(days=1),
        is_hard_deadline=True,
    )

    children = get_course_index(user=user, course=course, can_access_content=True)

    assert children[0]["status"] == BLOCKED
    assert children[0]["url"] is None


@pytest.mark.django_db
@override_settings(DEADLINES_ACTIVE=True)
def test_soft_deadline_does_not_lock(mock_site_context):
    """Soft deadlines never change the access status."""
    course: Course = CourseFactory(title="Test Course", slug="test-course")
    topic = TopicFactory(title="Test Topic", slug="test-topic")
    user = UserFactory()
    course.items.create(child=topic, order=0)

    registration = _setup_cohort_registration(user, course)

    CohortDeadlineFactory(
        cohort_course_registration=registration,
        content_item=topic,
        deadline=timezone.now() - timedelta(days=1),
        is_hard_deadline=False,
    )

    children = get_course_index(user=user, course=course, can_access_content=True)

    # First item should be READY, not BLOCKED
    assert children[0]["status"] != BLOCKED


@pytest.mark.django_db
def test_no_deadlines_no_deadline_key(mock_site_context):
    """When no deadlines exist, child dicts have empty deadlines list."""
    course: Course = CourseFactory(title="Test Course", slug="test-course")
    topic = TopicFactory(title="Test Topic", slug="test-topic")
    user = UserFactory()
    course.items.create(child=topic, order=0)

    _setup_cohort_registration(user, course)

    children = get_course_index(user=user, course=course, can_access_content=True)

    assert children[0]["deadlines"] == []


@pytest.mark.django_db
@override_settings(DEADLINES_ACTIVE=True)
def test_view_course_item_redirects_if_locked(client, mock_site_context):
    """A deadline-locked item redirects to the loop-free detail page.

    Not to course_home (now a resume redirector), which would loop straight
    back to the same locked item.
    """
    course: Course = CourseFactory(title="Test Course", slug="test-course")
    topic = TopicFactory(title="Test Topic", slug="test-topic")
    user = UserFactory()
    course.items.create(child=topic, order=0)

    registration = _setup_cohort_registration(user, course)

    CohortDeadlineFactory(
        cohort_course_registration=registration,
        content_item=topic,
        deadline=timezone.now() - timedelta(days=1),
        is_hard_deadline=True,
    )

    client.force_login(user)
    url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    response = client.get(url)

    assert response.status_code == 302
    assert response.url == reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )


@pytest.mark.django_db
@override_settings(DEADLINES_ACTIVE=False)
def test_get_course_index_skips_deadlines_when_inactive(mock_site_context):
    """When DEADLINES_ACTIVE=False, deadlines list is empty and item is not BLOCKED."""
    course: Course = CourseFactory(title="Test Course", slug="test-course")
    topic = TopicFactory(title="Test Topic", slug="test-topic")
    user = UserFactory()
    course.items.create(child=topic, order=0)

    registration = _setup_cohort_registration(user, course)

    CohortDeadlineFactory(
        cohort_course_registration=registration,
        content_item=topic,
        deadline=timezone.now() - timedelta(days=1),
        is_hard_deadline=True,
    )

    children = get_course_index(user=user, course=course, can_access_content=True)

    assert children[0]["deadlines"] == []
    assert children[0]["status"] != BLOCKED


@pytest.mark.django_db
@override_settings(DEADLINES_ACTIVE=False)
def test_view_course_item_skips_lock_check_when_deadlines_inactive(
    client, mock_site_context
):
    """When DEADLINES_ACTIVE=False, expired hard deadline does not redirect."""
    course: Course = CourseFactory(title="Test Course", slug="test-course")
    topic = TopicFactory(title="Test Topic", slug="test-topic")
    user = UserFactory()
    course.items.create(child=topic, order=0)

    registration = _setup_cohort_registration(user, course)

    CohortDeadlineFactory(
        cohort_course_registration=registration,
        content_item=topic,
        deadline=timezone.now() - timedelta(days=1),
        is_hard_deadline=True,
    )

    client.force_login(user)
    url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    response = client.get(url)

    assert response.status_code == 200
    # The whole point of this test is that the user is *not* redirected and
    # the locked topic is still served. Strengthen by asserting the topic is
    # actually rendered, not just that some 200 response came back.
    assert response.context["topic"] == topic
    assert topic.title in response.content.decode()


# The co-branding chip the resolved organisation feeds into the course
# player's TOC header.
#
# organisation_for_learner_course itself is tested next to the other query
# helpers, in learner_management/tests/test_queries.py.


def _logo_upload(name: str = "logo.png") -> SimpleUploadedFile:
    buf = io.BytesIO()
    Image.new("RGB", (200, 100)).save(buf, format="PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


def _chip(response) -> str:
    """The rendered co-branding chip, on its own.

    Scoped to the element rather than searched across the whole player page,
    where decorative attributes such as aria-hidden appear on nearly every
    icon in the chrome and would satisfy the assertions by accident.
    """
    document = lxml.html.fromstring(response.content)
    elements = document.cssselect("#course-organisation-chip")
    assert elements, "no #course-organisation-chip in the response"
    return str(lxml.html.tostring(elements[0], encoding="unicode"))


@pytest.fixture
def player_response(mock_site_context, course_with_topic, logged_in_client):
    """The player's first item, for a learner registered through `organisation`."""

    def _get(organisation):
        course = course_with_topic()
        user = UserFactory()
        LearnerCourseRegistrationFactory(
            learner__user=user, course=course, learner__organisation=organisation
        )
        response = logged_in_client(user).get(
            reverse(
                "learner_interface:view_course_item",
                kwargs={"course_slug": course.slug, "index": 1},
            )
        )
        assert response.status_code == 200
        response.course = course
        return response

    return _get


@pytest.mark.django_db
class TestCourseOrganisationChip:
    """The resolved organisation reaches the player's TOC header as a chip:
    the logo when there is one, an initials monogram otherwise, with the
    organisation's name rendered as text beside it."""

    def test_logo_renders_with_the_organisation_name(self, player_response):
        organisation = OrganisationFactory(name="Acme Corp", logo=_logo_upload())

        chip = _chip(player_response(organisation))

        assert organisation.logo.url in chip
        assert "Acme Corp" in chip

    def test_logo_is_decorative_because_the_name_is_already_text(self, player_response):
        """Labelling the mark as well would announce the organisation twice."""
        organisation = OrganisationFactory(name="Acme Corp", logo=_logo_upload())

        chip = _chip(player_response(organisation))

        assert 'alt=""' in chip

    def test_chip_renders_above_the_course_title(self, player_response):
        """Co-branding sits above the title, not below it. Compared as sibling
        order inside the outline header, so restyling either element does not
        change what this asserts."""
        organisation = OrganisationFactory(name="Acme Corp", logo=_logo_upload())

        response = player_response(organisation)

        document = lxml.html.fromstring(response.content)
        chip = document.cssselect("#course-organisation-chip")[0]
        header = chip.getparent()
        titles = [
            element
            for element in header.iterchildren("p")
            if (element.text or "").strip() == response.course.title
        ]
        assert titles, "no course-title paragraph in the outline header"
        siblings = list(header)
        assert siblings.index(chip) < siblings.index(titles[0])

    def test_initials_monogram_renders_when_organisation_has_no_logo(
        self, player_response
    ):
        organisation = OrganisationFactory(name="Beta School")

        chip = _chip(player_response(organisation))

        assert organisation.initials in chip
        assert "Beta School" in chip

    def test_monogram_is_hidden_from_assistive_technology(self, player_response):
        """It repeats the name rendered beside it."""
        organisation = OrganisationFactory(name="Beta School")

        chip = _chip(player_response(organisation))

        assert 'aria-hidden="true"' in chip

    def test_no_chip_for_the_sites_default_organisation(
        self, mock_site_context, player_response
    ):
        """The default organisation stands for the site itself, which the
        surrounding chrome already brands — co-branding it would repeat that."""
        organisation = get_default_organisation(mock_site_context)
        organisation.name = "Renamed Away From The Site"
        organisation.save()

        response = player_response(organisation)

        document = lxml.html.fromstring(response.content)
        assert not document.cssselect("#course-organisation-chip")
        assert "Renamed Away From The Site" not in response.content.decode()
