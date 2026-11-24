import pytest

from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.content_engine.models import Course, Topic
from freedom_ls.learner_management.factories import LearnerCourseRegistrationFactory
from freedom_ls.learner_progress.factories import (
    CourseProgressFactory,
    TopicProgressFactory,
)
from freedom_ls.learner_progress.models import CourseProgress, TopicProgress
from freedom_ls.tests.retire import retire


@pytest.fixture
def three_topic_course(mock_site_context) -> tuple[Course, list[Topic]]:
    course: Course = CourseFactory(slug="outline-course")
    topics: list[Topic] = [
        TopicFactory(title=title) for title in ("First", "Second", "Third")
    ]
    for order, topic in enumerate(topics):
        course.items.create(child=topic, order=order)
    return course, topics


@pytest.fixture
def learner_client(three_topic_course: tuple[Course, list[Topic]]) -> Client:
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=three_topic_course[0])
    client = Client()
    client.force_login(user)
    return client


def _item_url(index: int) -> str:
    return reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": "outline-course", "index": index},
    )


@pytest.mark.django_db
def test_view_course_item_serves_the_next_topic_at_a_retired_topics_old_index(
    three_topic_course, learner_client
):
    _, (first, second, _) = three_topic_course
    retire(first)

    response = learner_client.get(_item_url(1))

    assert response.status_code == 200
    assert response.context["topic"] == second


@pytest.mark.django_db
def test_view_course_item_returns_404_past_the_end_of_the_shortened_outline(
    three_topic_course, learner_client
):
    _, (first, _, _) = three_topic_course
    retire(first)

    assert learner_client.get(_item_url(3)).status_code == 404


@pytest.mark.django_db
def test_retiring_a_topic_leaves_the_learners_progress_rows_unchanged(
    three_topic_course, learner_client
):
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
    three_topic_course, learner_client
):
    _, (first, _, _) = three_topic_course
    retire(first)
    Topic.objects.filter(pk=first.pk).update(retired_at=None)

    response = learner_client.get(_item_url(1))

    assert response.context["topic"] == first
