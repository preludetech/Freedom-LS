"""Undo deletes only the named item's completion for the named learner."""

from __future__ import annotations

from typing import cast

import pytest

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management import call_command

if "freedom_ls.qa_helpers" not in settings.INSTALLED_APPS:  # pragma: no cover
    pytest.skip("qa_helpers not installed", allow_module_level=True)

from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import Course
from freedom_ls.form_engine.factories import FormFactory
from freedom_ls.form_engine.models import FormProgress
from freedom_ls.learner_progress.factories import CourseProgressFactory
from freedom_ls.learner_progress.models import CourseProgress, TopicProgress

pytestmark = pytest.mark.dev_tooling


@pytest.fixture
def qa_site(mock_site_context) -> Site:
    site: Site = Site.objects.get_current()
    site.name = "DemoDev"
    site.save()
    return site


def _complete(record: CourseProgress, *titles: str) -> None:
    call_command(
        "qa_set_item_completion",
        "--learner",
        record.learner.user.email,
        "--course-slug",
        record.course.slug,
        *[arg for title in titles for arg in ("--item", title)],
        "--action",
        "complete",
    )


@pytest.mark.django_db
def test_undo_removes_only_the_named_items_of_the_named_learner(qa_site):
    course = cast(Course, CourseFactory(slug="qa-completion-course"))
    for title in ("Intro", "Outro"):
        ContentCollectionItemFactory(
            collection_object=course, child_object=TopicFactory(title=title)
        )
    ContentCollectionItemFactory(
        collection_object=course, child_object=FormFactory(title="Quiz")
    )
    record = cast(CourseProgress, CourseProgressFactory(course=course))
    bystander = cast(CourseProgress, CourseProgressFactory(course=course))
    _complete(record, "Intro", "Outro", "Quiz")
    _complete(bystander, "Intro", "Quiz")

    call_command(
        "qa_set_item_completion",
        "--learner",
        record.learner.user.email,
        "--course-slug",
        course.slug,
        "--item",
        "Intro",
        "--item",
        "Quiz",
        "--action",
        "undo",
    )

    titles = set(
        TopicProgress._base_manager.filter(course_progress=record).values_list(
            "topic__title", flat=True
        )
    )
    assert titles == {"Outro"}
    assert not FormProgress._base_manager.filter(user=record.learner.user).exists()
    assert TopicProgress._base_manager.filter(course_progress=bystander).count() == 1
    assert FormProgress._base_manager.filter(user=bystander.learner.user).count() == 1
    record.refresh_from_db()
    assert 0 < record.progress_percentage < 100
