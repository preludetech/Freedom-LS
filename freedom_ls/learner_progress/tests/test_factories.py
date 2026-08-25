"""Tests for learner_progress factories."""

import pytest

from django.contrib.sites.models import Site

from freedom_ls.content_engine.factories import TopicFactory
from freedom_ls.form_engine.factories import FormFactory
from freedom_ls.learner_progress.factories import (
    CourseFormAttemptFactory,
    CourseProgressFactory,
    TopicProgressFactory,
)
from freedom_ls.site_aware_models.models import _thread_locals


@pytest.mark.django_db
def test_course_form_attempt_factory_forwards_explicit_site_without_request_context(
    site: Site, mock_site_context: Site
) -> None:
    """An explicit ``site=`` must reach the nested form_progress row.

    Reproduces the qa_helpers management-command condition: prerequisites
    (``course_progress`` and ``form``) are built ahead of time, exactly as
    ``qa_complete_form`` fetches an already-resolved course progress record
    and form. The thread-local request is then cleared -- there is no
    ambient request inside a management command -- and only ``site=`` is
    passed explicitly to ``CourseFormAttemptFactory``, leaving
    ``form_progress`` for the factory to build. Without forwarding, that
    nested row falls back to a None site and violates the NOT NULL
    constraint on ``FormProgress.site``.
    """
    course_progress = CourseProgressFactory()
    form = FormFactory()
    delattr(_thread_locals, "request")

    attempt = CourseFormAttemptFactory(
        site=site,
        course_progress=course_progress,
        form=form,
        collection_item=None,
    )

    assert attempt.form_progress.site == site


@pytest.mark.django_db
def test_course_form_attempt_factory_forwards_site_to_default_collection_item(
    site: Site, mock_site_context: Site
) -> None:
    """The default-built collection_item must also carry the explicit site.

    ``collection_item`` shares the identical gap as ``form_progress``: it is
    a ``SubFactory`` onto another ``SiteAwareFactory`` that never forwards
    the parent's resolved site, so building it without an ambient request
    would otherwise hit the same NOT NULL constraint.
    """
    course_progress = CourseProgressFactory()
    form = FormFactory()
    delattr(_thread_locals, "request")

    attempt = CourseFormAttemptFactory(
        site=site,
        course_progress=course_progress,
        form=form,
    )

    assert attempt.collection_item is not None
    assert attempt.collection_item.site == site


@pytest.mark.django_db
def test_topic_progress_factory_forwards_site_to_default_collection_item(
    site: Site, mock_site_context: Site
) -> None:
    """TopicProgressFactory's collection_item shares the identical gap."""
    course_progress = CourseProgressFactory()
    topic = TopicFactory()
    delattr(_thread_locals, "request")

    topic_progress = TopicProgressFactory(
        site=site,
        course_progress=course_progress,
        topic=topic,
    )

    assert topic_progress.collection_item is not None
    assert topic_progress.collection_item.site == site
