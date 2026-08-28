from __future__ import annotations

import pytest

from django.contrib.staticfiles import finders

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import ContentCollectionItem, Course, Topic
from freedom_ls.form_engine.models import Form, FormProgress
from freedom_ls.learner_management.models import (
    CohortCourseRegistration,
    Learner,
    LearnerCourseRegistration,
)
from freedom_ls.learner_progress.factories import (
    CourseFormAttemptFactory,
    TopicProgressFactory,
)
from freedom_ls.learner_progress.models import CourseProgress, TopicProgress
from freedom_ls.learner_progress.utils import ensure_course_progress_record

# `static/vendor/tailwind.output.css` is a build artefact, not a checked-in file:
# extract_theme_tokens() reads it and build_report_html() calls that, so every
# test that renders a whole report needs `npm run tailwind_build` to have run.
# CI builds it before running pytest; a fresh clone has not.
requires_tailwind_bundle = pytest.mark.skipif(
    finders.find("vendor/tailwind.output.css") is None,
    reason="compiled Tailwind bundle missing -- run `npm run tailwind_build`",
)


def collection_item_for(course: Course, child: Form | Topic) -> ContentCollectionItem:
    """The collection item placing `child` in `course`.

    Read off a freshly loaded Course: `collection_items()` memoizes per
    instance, so a test that attaches more content between two lookups would
    otherwise be handed the list as it stood at the first one.
    """
    placed: Course = Course.objects.get(pk=course.pk)
    for collection_item in placed.viewable_collection_items():
        if collection_item.child == child:
            return collection_item
    raise AssertionError(f"{child} is not placed in {course}.")


def cohort_progress_record(
    registration: CohortCourseRegistration, user: User
) -> CourseProgress:
    """The record `registration` grants `user`, created if it is missing.

    The report is keyed on the Learner, so the record has to hang off the
    Learner row pairing the person with the cohort's organisation. The
    receivers that would mint it defer to ``transaction.on_commit``, which a
    rolled-back test transaction never reaches, so this calls the same service
    they call.
    """
    # _base_manager: a site-isolation test builds the other site's cohort while
    # the ambient site is still the first one, and SiteAwareManager would AND
    # that ambient site onto the lookup and miss the row.
    learner = Learner._base_manager.get(
        user=user, organisation=registration.cohort.organisation
    )
    return ensure_course_progress_record(learner, registration.course, registration)


def individual_progress_record(
    registration: LearnerCourseRegistration,
) -> CourseProgress:
    """The record an individual registration grants its own learner."""
    return ensure_course_progress_record(
        registration.learner, registration.course, registration
    )


def topic_progress(
    record: CourseProgress, topic: Topic, **fields: object
) -> TopicProgress:
    """A topic progress row at `topic`'s existing placement in `record`'s course.

    The placement is looked up rather than built: letting the factory mint a
    second collection item would place the topic in the course twice and
    double it in the report's completion denominator.
    """
    row: TopicProgress = TopicProgressFactory(
        course_progress=record,
        topic=topic,
        collection_item=collection_item_for(record.course, topic),
        **fields,
    )
    return row


def form_progress(record: CourseProgress, form: Form, **fields: object) -> FormProgress:
    """One sitting of `form` at its existing placement in `record`'s course.

    Attempt fields are forwarded to the form_engine row the sitting is made of,
    so callers still name `completed_time` and `scores` directly.
    """
    sitting: FormProgress = CourseFormAttemptFactory(
        course_progress=record,
        form=form,
        collection_item=collection_item_for(record.course, form),
        **{f"form_progress__{name}": value for name, value in fields.items()},
    ).form_progress
    return sitting
