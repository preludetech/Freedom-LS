"""Contracts of the post_save receiver that recalculates course progress.

test_course_progress.py covers the happy path — and doubles as the proof that the
receiver is connected at all. These pin the edges the receiver has to get right
that a save() override used to get for free.
"""

import pytest

from django.core import serializers
from django.utils import timezone

from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    TopicFactory,
)
from freedom_ls.form_engine.factories import FormFactory
from freedom_ls.form_engine.models import FormProgress
from freedom_ls.learner_progress.factories import (
    CourseFormAttemptFactory,
    CourseProgressFactory,
    TopicProgressFactory,
)
from freedom_ls.learner_progress.models import CourseProgress, TopicProgress


@pytest.fixture
def topic_placement(mock_site_context):
    """A record, and the collection item placing one topic in its course."""
    course = CourseFactory()
    record: CourseProgress = CourseProgressFactory(course=course)
    collection_item = ContentCollectionItemFactory(
        collection_object=course, child_object=TopicFactory(), order=0
    )
    return record, collection_item


@pytest.mark.django_db
def test_creating_an_already_complete_row_does_not_recalculate(topic_placement):
    """A row that arrives complete never made a transition."""
    record, collection_item = topic_placement

    TopicProgressFactory(
        course_progress=record,
        collection_item=collection_item,
        topic=collection_item.child,
        complete_time=timezone.now(),
    )

    record.refresh_from_db()
    assert record.progress_percentage == 0


@pytest.mark.django_db
def test_completing_a_form_recalculates_once(mock_site_context, monkeypatch):
    """complete() saves more than once, but it announces the completion once.

    The recalculation hangs off form_engine's `form_attempt_completed`, not off
    post_save, so the repeated saves inside complete() cannot each trigger one.
    """
    from freedom_ls.learner_progress import signals

    course = CourseFactory()
    form = FormFactory(strategy="QUIZ")
    collection_item = ContentCollectionItemFactory(
        collection_object=course, child_object=form, order=0
    )
    record: CourseProgress = CourseProgressFactory(course=course)

    calls = []
    monkeypatch.setattr(
        signals,
        "recalculate_progress_percentage",
        lambda course_progress: calls.append(course_progress),
    )

    fp: FormProgress = CourseFormAttemptFactory(
        course_progress=record,
        collection_item=collection_item,
        form=form,
    ).form_progress
    fp.complete()

    assert calls == [record]


@pytest.mark.django_db
def test_completing_a_form_sat_outside_a_course_recalculates_nothing(
    mock_site_context, monkeypatch
):
    """An attempt with no CourseFormAttempt has no percentage to move."""
    from freedom_ls.form_engine.factories import FormProgressFactory
    from freedom_ls.learner_progress import signals

    calls = []
    monkeypatch.setattr(
        signals,
        "recalculate_progress_percentage",
        lambda course_progress: calls.append(course_progress),
    )

    FormProgressFactory(form=FormFactory(strategy="QUIZ")).complete()

    assert calls == []


@pytest.mark.django_db
def test_queryset_update_does_not_recalculate(topic_placement):
    """post_save does not fire for queryset.update(), and callers are told so."""
    record, collection_item = topic_placement

    tp: TopicProgress = TopicProgressFactory(
        course_progress=record,
        collection_item=collection_item,
        topic=collection_item.child,
    )
    TopicProgress.objects.filter(pk=tp.pk).update(complete_time=timezone.now())

    record.refresh_from_db()
    assert record.progress_percentage == 0


@pytest.mark.django_db
def test_loaddata_does_not_recalculate(topic_placement):
    """A raw save writes exactly the fixture's rows and derives nothing extra.

    Passes with or without the receiver's `raw` guard today: the deserializer
    builds the instance with its completion time already set, so the transition
    check declines first. Pins the behaviour, not the guard.
    """
    record, collection_item = topic_placement

    tp: TopicProgress = TopicProgressFactory(
        course_progress=record,
        collection_item=collection_item,
        topic=collection_item.child,
    )
    tp.complete_time = timezone.now()
    serialized = serializers.serialize("json", [tp])
    TopicProgress.objects.filter(pk=tp.pk).delete()

    for deserialized in serializers.deserialize("json", serialized):
        deserialized.save()

    record.refresh_from_db()
    assert record.progress_percentage == 0


@pytest.mark.django_db
def test_recalculate_progress_percentage_catches_up_a_bulk_written_record(
    topic_placement,
):
    """The escape hatch bulk writers are told to call.

    Rows written already complete never fire the transition the receiver
    watches for, so a seeder or an import has to ask for the recalculation
    itself. Same result the receiver would have produced.
    """
    from freedom_ls.learner_progress.signals import recalculate_progress_percentage

    record, collection_item = topic_placement
    TopicProgressFactory(
        course_progress=record,
        collection_item=collection_item,
        topic=collection_item.child,
        complete_time=timezone.now(),
    )
    record.refresh_from_db()
    assert record.progress_percentage == 0

    recalculate_progress_percentage(record)

    record.refresh_from_db()
    assert record.progress_percentage == 100
