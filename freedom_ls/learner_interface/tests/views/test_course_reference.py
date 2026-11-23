"""The reference listing and reference topic pages of a course."""

from __future__ import annotations

import datetime

import lxml.html
import pytest
import time_machine
from pytest_django import DjangoAssertNumQueries
from pytest_mock import MockerFixture

from django.contrib.sites.models import Site
from django.db import connection
from django.http import HttpResponse
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    CoursePartFactory,
    CourseReferencePartFactory,
    FileFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import (
    Course,
    CourseAudience,
    CoursePart,
    CourseReferencePart,
    CourseVisibility,
    Topic,
)
from freedom_ls.deadlines.factories import (
    CourseDeadlineConfigFactory,
    CoursePauseFactory,
)
from freedom_ls.deadlines.models import AfterAccessEnded
from freedom_ls.form_engine.factories import FormFactory
from freedom_ls.learner_interface.templatetags.course_storage_keys import (
    course_part_storage_key,
)
from freedom_ls.learner_interface.tests.helpers import (
    form_attempt,
    set_due_date,
    topic_completion,
)
from freedom_ls.learner_management.factories import LearnerCourseRegistrationFactory
from freedom_ls.learner_progress.models import CourseProgress, TopicProgress
from freedom_ls.learner_progress.tests.helpers import course_progress_record
from freedom_ls.organisations.factories import OrganisationFactory

REFERENCE_QUERY_BOUND = 60
PLAYER_ITEMS = {"topic_item": 1, "form_item": 2}

REGISTERED_AT = datetime.datetime(2026, 3, 1, 10, 0, tzinfo=datetime.UTC)
AFTER_END = datetime.datetime(2026, 9, 1, 10, 0, tzinfo=datetime.UTC)

ANALYTICS_RECORDER = "freedom_ls.course_access.analytics_events.record_analytics_event"


def _reference_url(course: Course, route: str) -> str:
    """The listing URL, or for "topic" the URL of the first topic of the first reference part."""
    if route == "topic":
        part = course.reference_parts.all()[0].course_part
        topic = part.items.all()[0].child
        return reverse(
            "learner_interface:course_reference_topic",
            kwargs={
                "course_slug": course.slug,
                "part_slug": part.slug,
                "topic_slug": topic.slug,
            },
        )
    return reverse(
        "learner_interface:course_reference", kwargs={"course_slug": course.slug}
    )


def _topic_url(course: Course, part: CoursePart, topic_slug: str) -> str:
    return reverse(
        "learner_interface:course_reference_topic",
        kwargs={
            "course_slug": course.slug,
            "part_slug": part.slug,
            "topic_slug": topic_slug,
        },
    )


def _course_with_reference_topic() -> Course:
    course: Course = CourseFactory()
    _reference_part(course, TopicFactory(), order=0)
    return course


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


def _registered_client(course: Course) -> tuple[Client, User]:
    user: User = UserFactory()
    course_progress_record(course, user)
    client = Client()
    client.force_login(user)
    return client, user


def _page(response: HttpResponse) -> lxml.html.HtmlElement:
    return lxml.html.fromstring(response.content.decode())


def _ended_course(
    after_access_ended: AfterAccessEnded = AfterAccessEnded.NOTHING,
) -> Course:
    """A time-limited course whose access ended before AFTER_END, keeping no outline unless
    after_access_ended says otherwise."""
    course: Course = CourseFactory(time_limit_days=30)
    course.items.create(child=TopicFactory(), order=0)
    CourseDeadlineConfigFactory(
        course=course,
        end_course_access="on",
        after_access_ended=after_access_ended,
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
@pytest.mark.parametrize("route", ["listing", "topic"])
def test_an_anonymous_visitor_is_sent_to_login(
    mock_site_context: Site, route: str
) -> None:
    course = _course_with_reference_topic()

    response = Client().get(_reference_url(course, route))

    assert response.status_code == 302
    assert response["Location"].startswith(reverse("account_login"))


@pytest.mark.django_db
@pytest.mark.parametrize("route", ["listing", "topic"])
@pytest.mark.parametrize("state", ["unregistered", "paused", "ended"])
@time_machine.travel(AFTER_END, tick=False)
def test_a_learner_without_content_access_is_sent_to_the_detail_page(
    mock_site_context: Site, route: str, state: str
) -> None:
    course = _ended_course()
    _reference_part(course, TopicFactory(), order=0)
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
@pytest.mark.parametrize("route", ["listing", "topic"])
@pytest.mark.parametrize("hidden_or_outside", ["hidden", "outside_audience"])
def test_a_course_the_learner_cannot_see_is_a_404(
    mock_site_context: Site, route: str, hidden_or_outside: str
) -> None:
    course = _course_with_reference_topic()
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
@pytest.mark.parametrize("route", ["listing", "topic"])
def test_a_registered_learner_reads_the_page(
    mock_site_context: Site, route: str
) -> None:
    course = _course_with_reference_topic()
    client, _user = _registered_client(course)

    response = client.get(_reference_url(course, route))

    assert response.status_code == 200


@pytest.mark.django_db
def test_parts_and_topics_render_in_order_under_their_part_anchor(
    mock_site_context: Site,
) -> None:
    course = CourseFactory()
    later = _reference_part(
        course, TopicFactory(title="Zeta"), TopicFactory(title="Alpha"), order=1
    )
    earlier = _reference_part(course, TopicFactory(title="Middle"), order=0)
    _reference_part(course, order=2)
    client, _user = _registered_client(course)

    page = _page(client.get(_reference_url(course, "listing")))

    parts = page.cssselect(
        '#interface-main nav[aria-label="Reference topics"] > ul > li'
    )
    assert [part.get("id") for part in parts] == [earlier.slug, later.slug]
    assert [li.text_content().strip() for li in parts[1].cssselect("ul li")] == [
        "Zeta",
        "Alpha",
    ]


@pytest.mark.django_db
def test_the_listing_opens_every_part(mock_site_context: Site) -> None:
    course = CourseFactory()
    _reference_part(course, TopicFactory(), order=0)
    _reference_part(course, TopicFactory(), order=1)
    client, _user = _registered_client(course)

    page = _page(client.get(_reference_url(course, "listing")))

    parts = page.cssselect(
        '#interface-main nav[aria-label="Reference topics"] > ul > li'
    )
    assert [part.get("data-start-expanded") for part in parts] == ["true", "true"]


@pytest.mark.django_db
def test_listing_topic_titles_link_to_their_reference_topic_page(
    mock_site_context: Site,
) -> None:
    course = CourseFactory()
    topic = TopicFactory(title="Cheat sheet")
    part = _reference_part(course, topic, order=0)
    client, _user = _registered_client(course)

    page = _page(client.get(_reference_url(course, "listing")))

    link = page.cssselect(f'#interface-main li[id="{part.slug}"] ul a')[0]
    assert link.get("href") == _topic_url(course, part, topic.slug)


@pytest.mark.django_db
def test_a_part_holding_only_a_form_is_absent(mock_site_context: Site) -> None:
    course = CourseFactory()
    form_only = _reference_part(course, FormFactory(), order=0)
    client, _user = _registered_client(course)

    page = _page(client.get(_reference_url(course, "listing")))

    assert page.cssselect(f'[id="{form_only.slug}"]') == []


@pytest.mark.django_db
def test_with_no_reference_topics_the_page_says_so(mock_site_context: Site) -> None:
    course = CourseFactory()
    _reference_part(course, order=0)
    client, _user = _registered_client(course)

    page = _page(client.get(_reference_url(course, "listing")))

    assert "No reference material yet" in page.text_content()
    assert page.cssselect('#interface-main svg[data-icon="reference"]')
    assert page.cssselect('#interface-main nav[aria-label="Reference topics"]') == []


@pytest.mark.django_db
def test_the_breadcrumb_links_the_course_and_marks_reference_current(
    mock_site_context: Site,
) -> None:
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
def test_the_title_starts_with_reference_and_the_course(
    mock_site_context: Site,
) -> None:
    course = CourseFactory(title="Algebra")
    client, _user = _registered_client(course)

    page = _page(client.get(_reference_url(course, "listing")))

    assert page.findtext(".//title").strip().startswith("Reference — Algebra")


@pytest.mark.django_db
@pytest.mark.parametrize("route", ["listing", "topic"])
def test_reading_a_reference_page_changes_no_progress(
    mock_site_context: Site, mocker: MockerFixture, route: str
) -> None:
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

    client.get(_reference_url(course, route))

    record.refresh_from_db()
    assert (
        TopicProgress.objects.count(),
        record.last_accessed_item,
        record.last_accessed_time,
        record.started_at,
    ) == before
    recorder.assert_not_called()


@pytest.mark.django_db
@pytest.mark.parametrize("route", ["listing", "topic"])
def test_reading_a_reference_page_creates_no_course_progress_record(
    mock_site_context: Site, route: str
) -> None:
    course = CourseFactory(access_config={"access_type": "free"})
    _reference_part(course, TopicFactory(), order=0)
    client = Client()
    client.force_login(UserFactory())
    CourseProgress.objects.all().delete()

    client.get(_reference_url(course, route))

    assert not CourseProgress.objects.filter(course=course).exists()


@pytest.mark.django_db
@pytest.mark.parametrize(("parts", "topics"), [(1, 1), (3, 3)])
@pytest.mark.parametrize("route", ["listing", "topic"])
def test_the_query_count_does_not_grow_with_content(
    mock_site_context: Site,
    django_assert_max_num_queries: DjangoAssertNumQueries,
    parts: int,
    topics: int,
    route: str,
) -> None:
    course = CourseFactory()
    for order in range(parts):
        _reference_part(course, *[TopicFactory() for _ in range(topics)], order=order)
    client, _user = _registered_client(course)

    with django_assert_max_num_queries(REFERENCE_QUERY_BOUND):
        client.get(_reference_url(course, route))


def _topic_course() -> tuple[Course, CoursePart, list[Topic]]:
    """A course with a first part of three topics and a later part of one."""
    course: Course = CourseFactory(title="Algebra")
    topics: list[Topic] = [TopicFactory(title=name) for name in ("One", "Two", "Three")]
    part = _reference_part(course, *topics, order=0, title="Formulas")
    _reference_part(course, TopicFactory(title="Elsewhere"), order=1)
    return course, part, topics


@pytest.mark.django_db
@pytest.mark.parametrize(
    "missing",
    ["other_course_part", "topic_outside_part", "form_child", "form_only_part"],
)
def test_anything_outside_the_courses_reference_parts_is_a_404(
    mock_site_context: Site, missing: str
) -> None:
    course, part, _topics = _topic_course()
    other_course = CourseFactory()
    foreign = _reference_part(other_course, TopicFactory(), order=0)
    form = FormFactory()
    ContentCollectionItemFactory(collection_object=part, child_object=form, order=9)
    form_only = _reference_part(course, FormFactory(), order=5)
    outside = TopicFactory()
    urls = {
        "other_course_part": _topic_url(
            course, foreign, foreign.items.get().child.slug
        ),
        "topic_outside_part": _topic_url(course, part, outside.slug),
        "form_child": _topic_url(course, part, form.slug),
        "form_only_part": _topic_url(
            course, form_only, form_only.items.get().child.slug
        ),
    }
    client, _user = _registered_client(course)

    response = client.get(urls[missing])

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_middle_topic_links_to_its_neighbours_in_the_part(
    mock_site_context: Site,
) -> None:
    course, part, topics = _topic_course()
    client, _user = _registered_client(course)

    page = _page(client.get(_topic_url(course, part, topics[1].slug)))

    footer = page.cssselect('nav[aria-label="Reference topics"]')[0]
    previous, following = footer.cssselect("a")
    assert previous.get("href") == _topic_url(course, part, topics[0].slug)
    assert previous.get("aria-label") == "Previous: One"
    assert following.get("href") == _topic_url(course, part, topics[2].slug)
    assert following.get("aria-label") == "Next: Three"


@pytest.mark.django_db
def test_the_first_topic_has_no_previous(mock_site_context: Site) -> None:
    course, part, topics = _topic_course()
    client, _user = _registered_client(course)

    page = _page(client.get(_topic_url(course, part, topics[0].slug)))

    labels = [
        a.get("aria-label")
        for a in page.cssselect('nav[aria-label="Reference topics"] a')
    ]
    assert labels == ["Next: Two"]


@pytest.mark.django_db
def test_the_last_topic_has_no_next_even_when_a_later_part_has_topics(
    mock_site_context: Site,
) -> None:
    course, part, topics = _topic_course()
    client, _user = _registered_client(course)

    page = _page(client.get(_topic_url(course, part, topics[2].slug)))

    labels = [
        a.get("aria-label")
        for a in page.cssselect('nav[aria-label="Reference topics"] a')
    ]
    assert labels == ["Previous: Two"]


@pytest.mark.django_db
def test_the_breadcrumb_and_back_link_point_at_the_reference_pages(
    mock_site_context: Site,
) -> None:
    course, part, topics = _topic_course()
    client, _user = _registered_client(course)
    listing = reverse(
        "learner_interface:course_reference", kwargs={"course_slug": course.slug}
    )

    page = _page(client.get(_topic_url(course, part, topics[0].slug)))

    crumbs = page.cssselect('nav[aria-label="Breadcrumb"] a')
    assert [crumb.get("href") for crumb in crumbs] == [
        reverse("learner_interface:course_home", kwargs={"course_slug": course.slug}),
        listing,
        f"{listing}#{part.slug}",
    ]
    back = [a for a in page.cssselect("#interface-main a") if a.get("href") == listing]
    assert back


@pytest.mark.django_db
def test_a_reference_topic_has_no_progress_controls(mock_site_context: Site) -> None:
    course, part, topics = _topic_course()
    client, _user = _registered_client(course)

    response = client.get(_topic_url(course, part, topics[1].slug))
    page = _page(response)

    assert page.cssselect('[name="mark_complete"]') == []
    assert "Finish Course" not in response.content.decode()
    assert page.cssselect('#interface-main form[method="post"]') == []


@pytest.mark.django_db
def test_the_topic_title_is_topic_part_course_site(mock_site_context: Site) -> None:
    course, part, topics = _topic_course()
    client, _user = _registered_client(course)

    page = _page(client.get(_topic_url(course, part, topics[0].slug)))

    title = page.findtext(".//title").strip()
    assert title.startswith("One — Formulas — Algebra — ")


@pytest.mark.django_db
def test_a_shared_topic_resolves_media_from_its_own_directory(
    mock_site_context: Site,
) -> None:
    course = CourseFactory()
    topic = TopicFactory(
        file_path="shared/formulas/topic.md",
        content='<c-picture src="images/x.svg" alt="A diagram"></c-picture>',
    )
    _reference_part(course, topic, order=0)
    stored = FileFactory(
        file_path="shared/formulas/images/x.svg", mime_type="image/svg+xml"
    )
    client, _user = _registered_client(course)

    response = client.get(_reference_url(course, "topic"))

    assert stored.file.url in response.content.decode()


def _toc_links(response: HttpResponse) -> list[lxml.html.HtmlElement]:
    """The links to the reference listing inside the outline region."""
    course = response.context["course"]
    href = reverse(
        "learner_interface:course_reference", kwargs={"course_slug": course.slug}
    )
    return [
        link
        for link in _page(response).cssselect("#course-toc-region a")
        if link.get("href") == href
    ]


def _player_course_with_reference() -> Course:
    """A course of a topic then a form, with one reference topic."""
    course: Course = CourseFactory()
    course.items.create(child=TopicFactory(), order=0)
    course.items.create(child=FormFactory(), order=1)
    _reference_part(course, TopicFactory(), order=0)
    return course


def _player_url(course: Course, name: str) -> str:
    """A player page: "topic_item" and "form_item" open items 1 and 2."""
    kwargs: dict[str, object] = {"course_slug": course.slug}
    if name in PLAYER_ITEMS:
        kwargs["index"] = PLAYER_ITEMS[name]
        name = "view_course_item"
    return reverse(f"learner_interface:{name}", kwargs=kwargs)


@pytest.mark.django_db
@pytest.mark.parametrize("route", ["topic_item", "form_item", "course_finish"])
def test_the_reference_link_shows_on_player_pages(
    mock_site_context: Site, route: str
) -> None:
    course = _player_course_with_reference()
    client, user = _registered_client(course)
    # A form item stays shut until the topic before it is complete.
    topic_completion(
        course, user, course.viewable_items()[0], complete_time=REGISTERED_AT
    )

    response = client.get(_player_url(course, route))

    assert len(_toc_links(response)) == 1


@pytest.mark.django_db
def test_the_reference_link_shows_on_a_closed_item_page(
    mock_site_context: Site,
) -> None:
    course = _player_course_with_reference()
    set_due_date(course, course.viewable_items()[0], due_date=datetime.date(2020, 1, 1))
    CourseDeadlineConfigFactory(course=course, close_items="on")
    client, _user = _registered_client(course)

    response = client.get(_player_url(course, "topic_item"))

    assert "learner_interface/course_item_closed.html" in [
        template.name for template in response.templates
    ]
    assert len(_toc_links(response)) == 1


@pytest.mark.django_db
def test_the_reference_link_shows_on_a_paused_learners_completed_topic(
    mock_site_context: Site,
) -> None:
    course = _player_course_with_reference()
    client = _paused(course)
    user = CourseProgress.objects.get(course=course).learner.user
    topic_completion(
        course, user, course.viewable_items()[0], complete_time=REGISTERED_AT
    )

    response = client.get(_player_url(course, "topic_item"))

    assert len(_toc_links(response)) == 1


@pytest.mark.django_db
def test_the_reference_link_shows_for_a_course_with_an_empty_learning_path(
    mock_site_context: Site,
) -> None:
    course = _course_with_reference_topic()
    client, _user = _registered_client(course)

    response = client.get(_reference_url(course, "listing"))

    assert len(_toc_links(response)) == 1


@pytest.mark.django_db
def test_the_reference_link_survives_a_boosted_request(mock_site_context: Site) -> None:
    course = _player_course_with_reference()
    client, _user = _registered_client(course)

    response = client.get(_player_url(course, "topic_item"), HTTP_HX_REQUEST="true")

    assert len(_toc_links(response)) == 1


@pytest.mark.django_db
def test_the_reference_link_is_absent_for_a_course_without_reference_parts(
    mock_site_context: Site,
) -> None:
    course = _player_course_with_reference()
    course.reference_parts.all().delete()
    client, _user = _registered_client(course)

    response = client.get(_player_url(course, "topic_item"))

    assert _toc_links(response) == []


@pytest.mark.django_db
@time_machine.travel(AFTER_END, tick=False)
def test_the_reference_link_is_absent_where_an_ended_learner_keeps_no_outline(
    mock_site_context: Site,
) -> None:
    course = _ended_course()
    form = FormFactory()
    course.items.create(child=form, order=1)
    _reference_part(course, TopicFactory(), order=0)
    client = _ended(course)
    user = CourseProgress.objects.get(course=course).learner.user
    form_attempt(course, user, form, completed_time=REGISTERED_AT)

    response = client.get(
        reverse(
            "learner_interface:course_form_complete",
            kwargs={"course_slug": course.slug, "index": 2},
        )
    )

    assert response.status_code == 200
    assert 'id="course-toc-region"' not in response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("route", "current"),
    [("listing", True), ("topic", False), ("player", False)],
)
def test_the_reference_link_is_current_only_on_reference_pages(
    mock_site_context: Site, route: str, current: bool
) -> None:
    course = _player_course_with_reference()
    client, _user = _registered_client(course)
    url = (
        _player_url(course, "topic_item")
        if route == "player"
        else _reference_url(course, route)
    )

    [link] = _toc_links(client.get(url))

    assert (link.get("aria-current") == "page") is current


@pytest.mark.django_db
def test_the_sidebar_lists_reference_parts_that_expand_to_topic_links(
    mock_site_context: Site,
) -> None:
    course = CourseFactory()
    course.items.create(child=TopicFactory(), order=0)
    topic = TopicFactory(title="Cheat sheet")
    part = _reference_part(course, topic, order=0)
    client, _user = _registered_client(course)

    page = _page(client.get(_player_url(course, "topic_item")))

    [outline] = page.cssselect('#course-toc-region nav[aria-label="Course outline"]')
    [reference] = page.cssselect('#course-toc-region nav[aria-label="Reference"]')
    [part_row] = reference.cssselect("ul > li[x-data='coursePart']")
    assert part.title in part_row.cssselect("button")[0].text_content()
    [link] = part_row.cssselect("ul a")
    assert link.text_content().strip() == "Cheat sheet"
    assert link.get("href") == _topic_url(course, part, topic.slug)
    assert part_row.get("data-contains-current") is None
    assert outline is not reference


@pytest.mark.django_db
def test_the_sidebar_marks_the_reference_topic_being_read(
    mock_site_context: Site,
) -> None:
    course = CourseFactory()
    first, second = TopicFactory(title="First"), TopicFactory(title="Second")
    part = _reference_part(course, first, second, order=0)
    client, _user = _registered_client(course)

    page = _page(client.get(_topic_url(course, part, second.slug)))

    [part_row] = page.cssselect(
        '#course-toc-region nav[aria-label="Reference"] li[x-data="coursePart"]'
    )
    assert part_row.get("data-contains-current") == "true"
    [current] = part_row.cssselect('[aria-current="page"]')
    assert current.text_content().strip() == "Second"


@pytest.mark.django_db
def test_reference_parts_keep_their_own_expanded_state_keys(
    mock_site_context: Site,
) -> None:
    course = _player_course_with_reference()
    client, _user = _registered_client(course)

    page = _page(client.get(_player_url(course, "topic_item")))

    [part_row] = page.cssselect(
        '#course-toc-region nav[aria-label="Reference"] li[x-data="coursePart"]'
    )
    part = course.reference_parts.get().course_part
    assert part_row.get("data-storage-key") == course_part_storage_key(
        course.slug, part.slug, "reference"
    )


def _sidebar_reference_rows(response: HttpResponse) -> list[lxml.html.HtmlElement]:
    """The reference topic rows in the outline panel."""
    rows: list[lxml.html.HtmlElement] = _page(response).cssselect(
        '#course-toc-region nav[aria-label="Reference"] li[x-data="coursePart"] ul li'
    )
    return rows


def _sidebar_reference_links(response: HttpResponse) -> list[lxml.html.HtmlElement]:
    """The links on the reference topic rows in the outline panel."""
    links: list[lxml.html.HtmlElement] = _page(response).cssselect(
        '#course-toc-region nav[aria-label="Reference"] li[x-data="coursePart"] ul a'
    )
    return links


@pytest.mark.django_db
def test_a_paused_learner_sees_reference_titles_without_links(
    mock_site_context: Site,
) -> None:
    course = _player_course_with_reference()
    client = _paused(course)
    user = CourseProgress.objects.get(course=course).learner.user
    topic_completion(
        course, user, course.viewable_items()[0], complete_time=REGISTERED_AT
    )

    response = client.get(_player_url(course, "topic_item"))

    assert len(_sidebar_reference_rows(response)) == 1
    assert _sidebar_reference_links(response) == []


@pytest.mark.django_db
@time_machine.travel(AFTER_END, tick=False)
def test_an_ended_learner_keeping_the_outline_sees_reference_titles_without_links(
    mock_site_context: Site,
) -> None:
    course = _ended_course(AfterAccessEnded.OUTLINE_AND_RESULTS)
    form = FormFactory()
    course.items.create(child=form, order=1)
    _reference_part(course, TopicFactory(), order=0)
    client = _ended(course)
    user = CourseProgress.objects.get(course=course).learner.user
    form_attempt(course, user, form, completed_time=REGISTERED_AT)

    response = client.get(
        reverse(
            "learner_interface:course_form_complete",
            kwargs={"course_slug": course.slug, "index": 2},
        )
    )

    assert len(_sidebar_reference_rows(response)) == 1
    assert _sidebar_reference_links(response) == []


@pytest.mark.django_db
def test_a_learner_with_content_access_sees_reference_topic_links(
    mock_site_context: Site,
) -> None:
    course = _player_course_with_reference()
    client, _user = _registered_client(course)

    response = client.get(_player_url(course, "topic_item"))

    assert len(_sidebar_reference_links(response)) == 1


@pytest.mark.django_db
@pytest.mark.parametrize("route", ["listing", "topic"])
def test_the_reference_sidebar_shows_the_learners_organisation(
    mock_site_context: Site, route: str
) -> None:
    course = _course_with_reference_topic()
    user = UserFactory()
    LearnerCourseRegistrationFactory(
        learner__user=user,
        course=course,
        learner__organisation=OrganisationFactory(name="Acme Corp"),
    )
    course_progress_record(course, user)
    client = Client()
    client.force_login(user)

    page = _page(client.get(_reference_url(course, route)))

    [chip] = page.cssselect("#course-toc-region #course-organisation-chip")
    assert "Acme Corp" in chip.text_content()


@pytest.mark.django_db
@pytest.mark.parametrize("route", ["listing", "topic"])
def test_the_reference_sidebar_shows_the_next_deadline(
    mock_site_context: Site, route: str
) -> None:
    course = _player_course_with_reference()
    client, _user = _registered_client(course)
    set_due_date(course, course.viewable_items()[0], due_date=datetime.date(2999, 1, 1))

    page = _page(client.get(_reference_url(course, route)))

    assert page.cssselect('#course-toc-region [data-testid="outline-deadline"]')


@pytest.mark.django_db
@pytest.mark.parametrize("route", ["listing", "topic"])
def test_a_reference_page_reads_the_reference_parts_once(
    mock_site_context: Site, route: str
) -> None:
    course = _course_with_reference_topic()
    client, _user = _registered_client(course)
    table = CourseReferencePart._meta.db_table
    url = _reference_url(course, route)

    with CaptureQueriesContext(connection) as queries:
        client.get(url)

    reads = [query for query in queries if f'FROM "{table}"' in query["sql"]]
    assert len(reads) == 1


@pytest.mark.django_db
def test_every_navigation_landmark_on_the_listing_has_its_own_name(
    mock_site_context: Site,
) -> None:
    course = _course_with_reference_topic()
    client, _user = _registered_client(course)

    page = _page(client.get(_reference_url(course, "listing")))

    names = [nav.get("aria-label") for nav in page.cssselect("nav[aria-label]")]
    assert len(names) == len(set(names))


@pytest.mark.django_db
def test_a_reference_parts_state_key_holds_when_an_earlier_part_gains_a_topic(
    mock_site_context: Site,
) -> None:
    course: Course = CourseFactory()
    course.items.create(child=TopicFactory(), order=0)
    earlier = _reference_part(course, order=0)
    part = _reference_part(course, TopicFactory(), order=1)
    ContentCollectionItemFactory(
        collection_object=earlier, child_object=TopicFactory(), order=0
    )
    client, _user = _registered_client(course)

    page = _page(client.get(_player_url(course, "topic_item")))

    keys = [
        row.get("data-storage-key")
        for row in page.cssselect(
            '#course-toc-region nav[aria-label="Reference"] li[x-data="coursePart"]'
        )
    ]
    assert keys[1] == course_part_storage_key(course.slug, part.slug, "reference")
