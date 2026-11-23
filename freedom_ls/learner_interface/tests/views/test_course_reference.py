"""The reference listing page of a course."""

from __future__ import annotations

import datetime

import lxml.html
import pytest
import time_machine

from django.http import HttpResponse
from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    CoursePartFactory,
    CourseReferencePartFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import (
    Course,
    CourseAudience,
    CoursePart,
    CourseVisibility,
)
from freedom_ls.deadlines.factories import (
    CourseDeadlineConfigFactory,
    CoursePauseFactory,
)
from freedom_ls.deadlines.models import AfterAccessEnded
from freedom_ls.form_engine.factories import FormFactory
from freedom_ls.learner_interface.tests.helpers import topic_completion
from freedom_ls.learner_progress.models import CourseProgress, TopicProgress
from freedom_ls.learner_progress.tests.helpers import course_progress_record
from freedom_ls.organisations.factories import OrganisationFactory

REFERENCE_QUERY_BOUND = 50

REGISTERED_AT = datetime.datetime(2026, 3, 1, 10, 0, tzinfo=datetime.UTC)
AFTER_END = datetime.datetime(2026, 9, 1, 10, 0, tzinfo=datetime.UTC)

ANALYTICS_RECORDER = "freedom_ls.course_access.analytics_events.record_analytics_event"


def _reference_url(course: Course, route: str) -> str:
    routes: dict[str, tuple[str, dict[str, str]]] = {
        "listing": ("learner_interface:course_reference", {}),
    }
    name, extra = routes[route]
    return reverse(name, kwargs={"course_slug": course.slug, **extra})


def _reference_part(
    course: Course, *children: object, order: int = 0, **part_fields: object
) -> CoursePart:
    """Attach a new part holding `children` in order to `course` as reference material."""
    part: CoursePart = CoursePartFactory(**part_fields)
    CourseReferencePartFactory(course=course, course_part=part, order=order)
    for position, child in enumerate(children):
        ContentCollectionItemFactory(
            collection_object=part, child_object=child, order=position
        )
    return part


def _registered_client(course: Course) -> tuple[Client, object]:
    user = UserFactory()
    course_progress_record(course, user)
    client = Client()
    client.force_login(user)
    return client, user


def _page(response: HttpResponse) -> lxml.html.HtmlElement:
    return lxml.html.fromstring(response.content.decode())


def _ended_course() -> Course:
    """A time-limited course whose access ended before AFTER_END and keeps no outline."""
    course: Course = CourseFactory(time_limit_days=30)
    course.items.create(child=TopicFactory(), order=0)
    CourseDeadlineConfigFactory(
        course=course,
        end_course_access="on",
        after_access_ended=AfterAccessEnded.NOTHING,
    )
    return course


def _ended(course: Course) -> Client:
    course_progress_record(course, UserFactory(), created_at=REGISTERED_AT)
    user = CourseProgress.objects.get(course=course).learner.user
    client = Client()
    client.force_login(user)
    return client


def _unregistered(course: Course) -> Client:
    client = Client()
    client.force_login(UserFactory())
    return client


def _paused(course: Course) -> Client:
    client, _user = _registered_client(course)
    CoursePauseFactory(course_progress=CourseProgress.objects.get(course=course))
    return client


@pytest.mark.django_db
@pytest.mark.parametrize("route", ["listing"])
def test_an_anonymous_visitor_is_sent_to_login(mock_site_context, route):
    course = CourseFactory()

    response = Client().get(_reference_url(course, route))

    assert response.status_code == 302
    assert response["Location"].startswith(reverse("account_login"))


@pytest.mark.django_db
@pytest.mark.parametrize("route", ["listing"])
@pytest.mark.parametrize("state", ["unregistered", "paused", "ended"])
@time_machine.travel(AFTER_END, tick=False)
def test_a_learner_without_content_access_is_sent_to_the_detail_page(
    mock_site_context, route, state
):
    course = _ended_course()
    if state == "ended":
        client = _ended(course)
    elif state == "paused":
        client = _paused(course)
    else:
        client = _unregistered(course)

    response = client.get(_reference_url(course, route))

    assert response.status_code == 302
    assert response["Location"] == reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )


@pytest.mark.django_db
@pytest.mark.parametrize("route", ["listing"])
@pytest.mark.parametrize("hidden_or_outside", ["hidden", "outside_audience"])
def test_a_course_the_learner_cannot_see_is_a_404(
    mock_site_context, route, hidden_or_outside
):
    course = CourseFactory()
    if hidden_or_outside == "hidden":
        course.visibility = CourseVisibility.HIDDEN
        course.save()
    else:
        course.audience = CourseAudience.ORGANISATION_LEARNERS
        course.save()
        course.organisations.add(OrganisationFactory())
    client = Client()
    client.force_login(UserFactory())

    response = client.get(_reference_url(course, route))

    assert response.status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize("route", ["listing"])
def test_a_registered_learner_reads_the_page(mock_site_context, route):
    course = CourseFactory()
    client, _user = _registered_client(course)

    response = client.get(_reference_url(course, route))

    assert response.status_code == 200


@pytest.mark.django_db
def test_parts_and_topics_render_in_order_under_their_part_anchor(mock_site_context):
    course = CourseFactory()
    later = _reference_part(
        course, TopicFactory(title="Zeta"), TopicFactory(title="Alpha"), order=1
    )
    earlier = _reference_part(course, TopicFactory(title="Middle"), order=0)
    _reference_part(course, order=2)
    client, _user = _registered_client(course)

    page = _page(client.get(_reference_url(course, "listing")))

    sections = page.cssselect("#interface-main section")
    assert [section.get("id") for section in sections] == [earlier.slug, later.slug]
    assert [li.text_content().strip() for li in sections[1].cssselect("li")] == [
        "Zeta",
        "Alpha",
    ]


@pytest.mark.django_db
def test_a_part_holding_only_a_form_is_absent(mock_site_context):
    course = CourseFactory()
    form_only = _reference_part(course, FormFactory(), order=0)
    client, _user = _registered_client(course)

    page = _page(client.get(_reference_url(course, "listing")))

    assert page.cssselect(f'section[id="{form_only.slug}"]') == []


@pytest.mark.django_db
def test_with_no_reference_topics_the_page_says_so(mock_site_context):
    course = CourseFactory()
    _reference_part(course, order=0)
    client, _user = _registered_client(course)

    page = _page(client.get(_reference_url(course, "listing")))

    assert "No reference material yet" in page.text_content()
    assert page.cssselect('#interface-main svg[data-icon="reference"]')
    assert page.cssselect("#interface-main section") == []


@pytest.mark.django_db
def test_the_breadcrumb_links_the_course_and_marks_reference_current(
    mock_site_context,
):
    course = CourseFactory()
    client, _user = _registered_client(course)

    page = _page(client.get(_reference_url(course, "listing")))

    course_crumb = page.cssselect('nav[aria-label="Breadcrumb"] a')[0]
    current = page.cssselect('nav[aria-label="Breadcrumb"] [aria-current="page"]')
    assert course_crumb.get("href") == reverse(
        "learner_interface:course_home", kwargs={"course_slug": course.slug}
    )
    assert [crumb.text_content().strip() for crumb in current] == ["Reference"]


@pytest.mark.django_db
def test_the_title_starts_with_reference_and_the_course(mock_site_context):
    course = CourseFactory(title="Algebra")
    client, _user = _registered_client(course)

    page = _page(client.get(_reference_url(course, "listing")))

    assert page.findtext(".//title").strip().startswith("Reference — Algebra")


@pytest.mark.django_db
def test_reading_the_listing_changes_no_progress(mock_site_context, mocker):
    course = CourseFactory()
    topic = TopicFactory()
    course.items.create(child=topic, order=0)
    _reference_part(course, TopicFactory(), order=0)
    client, user = _registered_client(course)
    topic_completion(course, user, topic)
    record = CourseProgress.objects.get(course=course)
    before = (
        TopicProgress.objects.count(),
        record.last_accessed_item,
        record.last_accessed_time,
        record.started_at,
    )
    recorder = mocker.patch(ANALYTICS_RECORDER)

    client.get(_reference_url(course, "listing"))

    record.refresh_from_db()
    assert (
        TopicProgress.objects.count(),
        record.last_accessed_item,
        record.last_accessed_time,
        record.started_at,
    ) == before
    recorder.assert_not_called()


@pytest.mark.django_db
def test_reading_the_listing_creates_no_course_progress_record(mock_site_context):
    course = CourseFactory(access_config={"access_type": "free"})
    _reference_part(course, TopicFactory(), order=0)
    client = Client()
    client.force_login(UserFactory())
    CourseProgress.objects.all().delete()

    client.get(_reference_url(course, "listing"))

    assert not CourseProgress.objects.filter(course=course).exists()


@pytest.mark.django_db
@pytest.mark.parametrize(("parts", "topics"), [(1, 1), (3, 3)])
def test_the_listing_query_count_does_not_grow_with_content(
    mock_site_context, django_assert_max_num_queries, parts, topics
):
    course = CourseFactory()
    for order in range(parts):
        _reference_part(course, *[TopicFactory() for _ in range(topics)], order=order)
    client, _user = _registered_client(course)

    with django_assert_max_num_queries(REFERENCE_QUERY_BOUND):
        client.get(_reference_url(course, "listing"))
