import pytest

from django.test import Client
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import (
    CourseFactory,
    CoursePartFactory,
    CourseReferencePartFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import Course, CoursePart, Topic
from freedom_ls.learner_interface.tests.helpers import topic_completion
from freedom_ls.learner_management.factories import LearnerCourseRegistrationFactory
from freedom_ls.learner_progress.factories import (
    CourseProgressFactory,
    TopicProgressFactory,
)
from freedom_ls.learner_progress.models import CourseProgress, TopicProgress
from freedom_ls.tests.retire import retire


@pytest.fixture
def three_topic_course(mock_site_context: object) -> tuple[Course, list[Topic]]:
    course: Course = CourseFactory(slug="outline-course")
    topics: list[Topic] = [
        TopicFactory(title=title) for title in ("First", "Second", "Third")
    ]
    for order, topic in enumerate(topics):
        course.items.create(child=topic, order=order)
    return course, topics


@pytest.fixture
def learner(three_topic_course: tuple[Course, list[Topic]]) -> User:
    user: User = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=three_topic_course[0])
    return user


@pytest.fixture
def learner_client(learner: User) -> Client:
    client = Client()
    client.force_login(learner)
    return client


def _item_url(index: int) -> str:
    return reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": "outline-course", "index": index},
    )


@pytest.mark.django_db
def test_view_course_item_serves_the_next_topic_at_a_retired_topics_old_index(
    three_topic_course: tuple[Course, list[Topic]], learner_client: Client
) -> None:
    _, (first, second, _) = three_topic_course
    retire(first)

    response = learner_client.get(_item_url(1))

    assert response.status_code == 200
    assert response.context["topic"] == second


@pytest.mark.django_db
def test_view_course_item_returns_404_past_the_end_of_the_shortened_outline(
    three_topic_course: tuple[Course, list[Topic]], learner_client: Client
) -> None:
    _, (first, _, _) = three_topic_course
    retire(first)

    assert learner_client.get(_item_url(3)).status_code == 404


@pytest.mark.django_db
def test_retiring_a_topic_leaves_the_learners_progress_rows_unchanged(
    three_topic_course: tuple[Course, list[Topic]], learner_client: Client
) -> None:
    course, (first, _, _) = three_topic_course
    course_progress = CourseProgressFactory(course=course)
    topic_progress = TopicProgressFactory(course_progress=course_progress, topic=first)
    before = (
        CourseProgress.objects.filter(pk=course_progress.pk).values().get(),
        TopicProgress.objects.filter(pk=topic_progress.pk).values().get(),
    )

    retire(first)
    learner_client.get(_item_url(1))

    assert before == (
        CourseProgress.objects.filter(pk=course_progress.pk).values().get(),
        TopicProgress.objects.filter(pk=topic_progress.pk).values().get(),
    )


@pytest.mark.django_db
def test_view_course_item_serves_a_topic_again_once_its_retired_at_is_cleared(
    three_topic_course: tuple[Course, list[Topic]], learner_client: Client
) -> None:
    _, (first, _, _) = three_topic_course
    retire(first)
    Topic.objects.filter(pk=first.pk).update(retired_at=None)

    response = learner_client.get(_item_url(1))

    assert response.context["topic"] == first


@pytest.mark.django_db
def test_view_course_item_previous_url_steps_back_over_the_shortened_outline(
    three_topic_course: tuple[Course, list[Topic]],
    learner: User,
    learner_client: Client,
) -> None:
    course, (first, second, _) = three_topic_course
    retire(first)
    topic_completion(course, learner, second, complete_time=timezone.now())

    response = learner_client.get(_item_url(2))

    assert response.context["previous_url"] == _item_url(1)


@pytest.mark.django_db
def test_view_course_item_is_last_after_the_final_live_topic(
    three_topic_course: tuple[Course, list[Topic]],
    learner: User,
    learner_client: Client,
) -> None:
    course, (first, _, third) = three_topic_course
    retire(third)
    topic_completion(course, learner, first, complete_time=timezone.now())

    response = learner_client.get(_item_url(2))

    assert response.context["is_last_item"] is True


@pytest.mark.django_db
def test_view_course_item_sidebar_numbers_the_child_after_a_retired_topic_from_one(
    three_topic_course: tuple[Course, list[Topic]], learner_client: Client
) -> None:
    _, (first, second, _) = three_topic_course
    retire(first)

    response = learner_client.get(_item_url(1))

    rows = response.context["course_index"]
    assert [(row["title"], row["url"]) for row in rows if row["url"]][:1] == [
        (second.title, _item_url(1))
    ]
    assert first.title not in [row["title"] for row in rows]


@pytest.fixture
def part_course(mock_site_context: object) -> tuple[Course, CoursePart, list[Topic]]:
    course: Course = CourseFactory(slug="outline-course")
    part: CoursePart = CoursePartFactory()
    course.items.create(child=part, order=0)
    topics: list[Topic] = [TopicFactory(title=title) for title in ("One", "Two")]
    for order, topic in enumerate(topics):
        part.items.create(child=topic, order=order)
    return course, part, topics


@pytest.mark.django_db
def test_view_course_item_breadcrumb_part_index_points_at_the_first_live_child(
    part_course: tuple[Course, CoursePart, list[Topic]],
) -> None:
    course, part, (first, second) = part_course
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course)
    client = Client()
    client.force_login(user)
    retire(first)

    response = client.get(_item_url(1))

    assert response.context["current_part"] == part
    assert response.context["current_part_index"] == 1
    assert response.context["topic"] == second


@pytest.mark.django_db
def test_view_course_item_sidebar_omits_a_retired_part_and_its_children(
    part_course: tuple[Course, CoursePart, list[Topic]], mock_site_context: object
) -> None:
    course, part, _ = part_course
    last = TopicFactory(title="After the part")
    course.items.create(child=last, order=1)
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course)
    client = Client()
    client.force_login(user)
    retire(part)

    response = client.get(_item_url(1))

    assert [row["title"] for row in response.context["course_index"]] == [last.title]
    assert response.context["topic"] == last


@pytest.fixture
def reference_course(
    mock_site_context: object,
) -> tuple[Course, CoursePart, list[Topic]]:
    course: Course = CourseFactory(slug="outline-course")
    part: CoursePart = CoursePartFactory(slug="glossary")
    CourseReferencePartFactory(course=course, course_part=part, order=0)
    topics: list[Topic] = [TopicFactory(slug=slug) for slug in ("alpha", "beta")]
    for order, topic in enumerate(topics):
        part.items.create(child=topic, order=order)
    return course, part, topics


def _reference_topic_url(part_slug: str, topic_slug: str) -> str:
    return reverse(
        "learner_interface:course_reference_topic",
        kwargs={
            "course_slug": "outline-course",
            "part_slug": part_slug,
            "topic_slug": topic_slug,
        },
    )


@pytest.fixture
def reference_client(
    reference_course: tuple[Course, CoursePart, list[Topic]],
) -> Client:
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=reference_course[0])
    client = Client()
    client.force_login(user)
    return client


@pytest.mark.django_db
def test_course_reference_topic_returns_404_for_a_retired_topic(
    reference_course: tuple[Course, CoursePart, list[Topic]], reference_client: Client
) -> None:
    _, _, (alpha, _) = reference_course
    retire(alpha)

    response = reference_client.get(_reference_topic_url("glossary", "alpha"))

    assert response.status_code == 404


@pytest.mark.django_db
def test_course_reference_topic_next_link_skips_a_retired_topic(
    reference_course: tuple[Course, CoursePart, list[Topic]], reference_client: Client
) -> None:
    _, _, (_, beta) = reference_course
    retire(beta)

    response = reference_client.get(_reference_topic_url("glossary", "alpha"))

    assert response.status_code == 200
    assert response.context["next_topic"] is None


@pytest.mark.django_db
def test_course_reference_topic_returns_404_for_a_retired_part(
    reference_course: tuple[Course, CoursePart, list[Topic]], reference_client: Client
) -> None:
    _, part, _ = reference_course
    retire(part)

    response = reference_client.get(_reference_topic_url("glossary", "alpha"))

    assert response.status_code == 404


@pytest.mark.django_db
def test_course_reference_lists_no_retired_part(
    reference_course: tuple[Course, CoursePart, list[Topic]], reference_client: Client
) -> None:
    course, part, _ = reference_course
    retire(part)

    response = reference_client.get(
        reverse(
            "learner_interface:course_reference", kwargs={"course_slug": course.slug}
        )
    )

    assert response.context["reference_outline"] == []
