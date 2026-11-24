"""A re-run replaces the scenario learners' sittings and leaves everyone else's."""

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
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
    QuestionOptionFactory,
)
from freedom_ls.form_engine.models import (
    Form,
    FormDeclaration,
    FormProgress,
    FormStrategy,
)
from freedom_ls.learner_progress.factories import CourseProgressFactory
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.qa_helpers.management.commands.qa_create_quiz_declaration_scenario import (
    COURSE_SLUG,
    DEFAULT_DECLARATION_QUIZ,
    OWN_DECLARATION_QUIZ,
    TOPIC_TITLE,
)

pytestmark = pytest.mark.dev_tooling


@pytest.fixture
def qa_site(mock_site_context) -> Site:
    site: Site = Site.objects.get_current()
    site.name = "DemoDev"
    site.save()
    return site


def _quiz(title: str) -> Form:
    form = cast(
        Form,
        FormFactory(
            title=title,
            strategy=FormStrategy.QUIZ,
            quiz_pass_percentage=50,
            requires_declaration=True,
        ),
    )
    page = FormPageFactory(form=form)
    for order in range(2):
        question = FormQuestionFactory(form_page=page, order=order)
        QuestionOptionFactory(question=question, correct=True, value="right")
        QuestionOptionFactory(question=question, correct=False, value="wrong")
    return form


def _course() -> Course:
    course = cast(Course, CourseFactory(slug=COURSE_SLUG))
    ContentCollectionItemFactory(
        collection_object=course, child_object=TopicFactory(title=TOPIC_TITLE)
    )
    for title in (OWN_DECLARATION_QUIZ, DEFAULT_DECLARATION_QUIZ):
        ContentCollectionItemFactory(
            collection_object=course, child_object=_quiz(title)
        )
    return course


def _run() -> None:
    call_command(
        "qa_create_quiz_declaration_scenario",
        "DemoDev",
        "--email-a",
        "qa-a@example.com",
        "--email-b",
        "qa-b@example.com",
        "--email-c",
        "qa-c@example.com",
        "--extra-course-slug",
        COURSE_SLUG,
    )


@pytest.mark.django_db
def test_rerun_resets_scenario_sittings_and_spares_other_learners(qa_site):
    course = _course()
    bystander = cast(CourseProgress, CourseProgressFactory(course=course))
    own_quiz = Form.objects.get(title=OWN_DECLARATION_QUIZ)
    FormProgress.objects.create(user=bystander.learner.user, form=own_quiz)

    _run()
    _run()

    rows = FormProgress._base_manager.filter(form__in=Form.objects.all())
    assert not rows.filter(user__email="qa-a@example.com").exists()
    [open_sitting] = rows.filter(user__email="qa-b@example.com")
    assert open_sitting.completed_time is None
    assert not FormDeclaration._base_manager.filter(form_progress=open_sitting).exists()
    sittings_c = rows.filter(user__email="qa-c@example.com")
    assert sittings_c.count() == 2
    failed = sittings_c.get(form__title=DEFAULT_DECLARATION_QUIZ)
    assert failed.completed_time is not None
    assert failed.passed() is False
    assert FormDeclaration._base_manager.filter(form_progress=failed).exists()
    assert rows.filter(user=bystander.learner.user).count() == 1
