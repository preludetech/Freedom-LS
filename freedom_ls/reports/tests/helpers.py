"""Helpers shared by the report tests: progress rows placed in a course and the
compiled-Tailwind skip mark."""

from __future__ import annotations

import pytest

from django.contrib.staticfiles import finders

from freedom_ls.content_engine.models import Topic
from freedom_ls.content_engine.tests.helpers import collection_item_for
from freedom_ls.form_engine.models import Form, FormProgress
from freedom_ls.learner_progress.factories import (
    CourseFormAttemptFactory,
    TopicProgressFactory,
)
from freedom_ls.learner_progress.models import CourseProgress, TopicProgress

# `static/vendor/tailwind.output.css` is a build artefact, not a checked-in file:
# extract_theme_tokens() reads it and build_report_html() calls that, so every
# test that renders a whole report needs `npm run tailwind_build` to have run.
# CI builds it before running pytest; a fresh clone has not.
requires_tailwind_bundle = pytest.mark.skipif(
    finders.find("vendor/tailwind.output.css") is None,
    reason="compiled Tailwind bundle missing -- run `npm run tailwind_build`",
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
