"""Tests for prev/next navigation in view_course_item under the viewable-only index scheme."""

import pytest

from django.test import Client
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    CoursePartFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import Course, CoursePart
from freedom_ls.form_engine.factories import FormFactory
from freedom_ls.learner_progress.models import TopicProgress

from .conftest import (
    course_progress_record,
    form_attempt,
    register_user_for_course,
    topic_completion,
)


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
