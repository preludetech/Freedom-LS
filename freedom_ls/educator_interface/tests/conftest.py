"""Fixtures shared across the educator interface tests."""

from __future__ import annotations

import pytest

from django.utils import timezone

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import ContentCollectionItem, Course, Topic
from freedom_ls.form_engine.models import Form
from freedom_ls.learner_management.models import CohortCourseRegistration, Learner
from freedom_ls.learner_progress.factories import TopicProgressFactory
from freedom_ls.learner_progress.models import CourseProgress, TopicProgress
from freedom_ls.learner_progress.utils import ensure_course_progress_record
from freedom_ls.organisations.factories import OrganisationFactory


@pytest.fixture
def panel_request(site_aware_request):
    """A request carrying panel_url_kwargs for a real organisation.

    Tables and panels rendered standalone still build links into
    educator_interface:interface, which takes an organisation_slug. The
    interface() view sets these kwargs before dispatch; a test rendering the
    component on its own has to supply them.
    """

    def _make(path: str = "/"):
        organisation = OrganisationFactory()
        request = site_aware_request.get(path)
        request.panel_url_kwargs = {"organisation_slug": organisation.slug}
        request.organisation = organisation
        return request

    return _make


def collection_item_for(course: Course, child: Form | Topic) -> ContentCollectionItem:
    """The collection item placing `child` in `course`."""
    for collection_item in course.viewable_collection_items():
        if collection_item.child == child:
            return collection_item
    raise AssertionError(f"{child} is not placed in {course}.")


def cohort_progress_record(
    registration: CohortCourseRegistration, user: User, **fields: object
) -> CourseProgress:
    """The record `registration` grants `user`, created if it is missing.

    The educator matrix is keyed on the registration rather than on the
    person, so a test that wants a particular percentage has to say which
    registration it belongs to. The receivers that would mint the record defer
    to ``transaction.on_commit``, which a rolled-back test transaction never
    reaches, so this calls the same service they call.
    """
    learner = Learner.objects.get(
        user=user, organisation=registration.cohort.organisation
    )
    record = ensure_course_progress_record(learner, registration.course, registration)
    if fields:
        for name, value in fields.items():
            setattr(record, name, value)
        record.save(update_fields=list(fields))
    return record


def complete_topic_in_record(record: CourseProgress, topic: Topic) -> TopicProgress:
    """Complete `topic` where it sits in `record`'s course, under that record.

    Saving a completed row is what drives the percentage recalculation, so the
    record's figure and its cells always come from the same event.
    """
    completion: TopicProgress = TopicProgressFactory(
        course_progress=record,
        collection_item=collection_item_for(record.course, topic),
        topic=topic,
    )
    completion.complete_time = timezone.now()
    completion.save()
    return completion
