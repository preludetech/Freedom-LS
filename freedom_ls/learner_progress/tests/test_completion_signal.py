"""Contracts of the post_save receiver that recalculates course progress.

test_course_progress.py covers the happy path — and doubles as the proof that the
receiver is connected at all. These pin the edges the receiver has to get right
that a save() override used to get for free.
"""

import pytest

from django.core import serializers
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    FormFactory,
    TopicFactory,
)
from freedom_ls.learner_progress.factories import (
    CourseProgressFactory,
    FormProgressFactory,
    TopicProgressFactory,
)
from freedom_ls.learner_progress.models import (
    CourseProgress,
    FormProgress,
    TopicProgress,
)


@pytest.mark.django_db
def test_creating_an_already_complete_row_does_not_recalculate(mock_site_context):
    """A row that arrives complete never made a transition.

    The qa_helpers seeding commands depend on this: the recalculation creates
    CourseProgress without a site, so firing here would raise NotNullViolation.
    """
    user = UserFactory()
    course = CourseFactory()
    topic = TopicFactory()
    ContentCollectionItemFactory(collection_object=course, child_object=topic, order=0)

    TopicProgressFactory(user=user, topic=topic, complete_time=timezone.now())

    assert not CourseProgress.objects.filter(user=user, course=course).exists()


@pytest.mark.django_db
def test_completing_a_form_recalculates_once(mock_site_context, monkeypatch):
    """complete() saves three times over one completion, but it is one completion."""
    from freedom_ls.learner_progress import signals

    user = UserFactory()
    course = CourseFactory()
    form = FormFactory(strategy="QUIZ")
    ContentCollectionItemFactory(collection_object=course, child_object=form, order=0)
    CourseProgressFactory(user=user, course=course)

    calls = []
    monkeypatch.setattr(
        signals,
        "update_course_progress_on_completion",
        lambda user, content_item: calls.append((user, content_item)),
    )

    fp: FormProgress = FormProgressFactory(user=user, form=form)
    fp.complete()

    assert len(calls) == 1


@pytest.mark.django_db
def test_queryset_update_does_not_recalculate(mock_site_context):
    """post_save does not fire for queryset.update(), and callers are told so."""
    user = UserFactory()
    course = CourseFactory()
    topic = TopicFactory()
    ContentCollectionItemFactory(collection_object=course, child_object=topic, order=0)
    course_progress: CourseProgress = CourseProgressFactory(user=user, course=course)

    tp: TopicProgress = TopicProgressFactory(user=user, topic=topic)
    TopicProgress.objects.filter(pk=tp.pk).update(complete_time=timezone.now())

    course_progress.refresh_from_db()
    assert course_progress.progress_percentage == 0


@pytest.mark.django_db
def test_loaddata_does_not_recalculate(mock_site_context):
    """A raw save writes exactly the fixture's rows and derives nothing extra.

    Passes with or without the receiver's `raw` guard today: the deserializer
    builds the instance with its completion time already set, so the transition
    check declines first. Pins the behaviour, not the guard.
    """
    user = UserFactory()
    course = CourseFactory()
    topic = TopicFactory()
    ContentCollectionItemFactory(collection_object=course, child_object=topic, order=0)

    tp: TopicProgress = TopicProgressFactory(user=user, topic=topic)
    tp.complete_time = timezone.now()
    serialized = serializers.serialize("json", [tp])
    TopicProgress.objects.filter(pk=tp.pk).delete()

    for deserialized in serializers.deserialize("json", serialized):
        deserialized.save()

    assert not CourseProgress.objects.filter(user=user, course=course).exists()
