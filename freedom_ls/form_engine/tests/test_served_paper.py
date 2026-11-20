"""The served paper written once when a quiz sitting starts."""

from __future__ import annotations

from datetime import timedelta

import pytest

from django.utils import timezone

from freedom_ls.form_engine.factories import (
    FormContentFactory,
    FormFactory,
    FormPageFactory,
    FormProgressFactory,
    FormQuestionFactory,
    QuestionOptionFactory,
    served_paper_of,
)
from freedom_ls.form_engine.models import Form, FormProgress, FormStrategy
from freedom_ls.form_engine.served_paper import (
    build_served_paper,
    ensure_served_paper,
    served_child_ids,
)


@pytest.fixture
def quiz_form(mock_site_context: object) -> Form:
    form: Form = FormFactory(strategy=FormStrategy.QUIZ)
    page_one = FormPageFactory(form=form, order=0)
    page_two = FormPageFactory(form=form, order=1)
    FormContentFactory(form_page=page_one, order=0)
    question = FormQuestionFactory(form_page=page_one, order=1)
    QuestionOptionFactory(question=question, order=0)
    QuestionOptionFactory(question=question, order=1)
    FormQuestionFactory(form_page=page_two, order=0, type="short_text")
    return form


@pytest.mark.django_db
def test_build_served_paper_lists_pages_children_and_options_in_authored_order(
    quiz_form: Form,
) -> None:
    page_one, page_two = quiz_form.pages.all()
    content = page_one.text_items.get()
    question = page_one.questions.get()
    option_one, option_two = question.options.all()
    unanswerable = page_two.questions.get()

    paper = build_served_paper(quiz_form)

    assert paper["pages"] == [
        {"id": str(page_one.id), "children": [str(content.id), str(question.id)]},
        {"id": str(page_two.id), "children": [str(unanswerable.id)]},
    ]
    assert paper["options"] == {
        str(question.id): [str(option_one.id), str(option_two.id)]
    }


@pytest.mark.django_db
def test_build_served_paper_gives_a_question_without_options_no_entry(
    quiz_form: Form,
) -> None:
    question_without_options = quiz_form.pages.all()[1].questions.get()

    paper = build_served_paper(quiz_form)

    assert str(question_without_options.id) not in paper["options"]


@pytest.mark.django_db
def test_build_served_paper_seed_is_a_non_negative_int_below_two_to_the_63(
    quiz_form: Form,
) -> None:
    paper = build_served_paper(quiz_form)

    assert 0 <= paper["seed"] < 2**63


@pytest.mark.django_db
def test_ensure_served_paper_writes_for_an_open_quiz_sitting(quiz_form: Form) -> None:
    progress = FormProgressFactory(form=quiz_form)

    ensure_served_paper(progress)

    stored = FormProgress.objects.get(pk=progress.pk).served_paper
    assert stored is not None
    assert progress.served_paper == stored
    assert [page["id"] for page in stored["pages"]] == [
        str(page.id) for page in quiz_form.pages.all()
    ]


@pytest.mark.django_db
def test_ensure_served_paper_does_nothing_for_a_non_quiz_form(
    mock_site_context,
) -> None:
    form = FormFactory(strategy=FormStrategy.CATEGORY_VALUE_SUM)
    FormPageFactory(form=form)
    progress = FormProgressFactory(form=form)

    ensure_served_paper(progress)

    assert FormProgress.objects.get(pk=progress.pk).served_paper is None


@pytest.mark.django_db
def test_ensure_served_paper_does_nothing_for_a_completed_sitting(
    quiz_form: Form,
) -> None:
    progress = FormProgressFactory(form=quiz_form, completed_time=timezone.now())

    ensure_served_paper(progress)

    assert FormProgress.objects.get(pk=progress.pk).served_paper is None


@pytest.mark.django_db
def test_ensure_served_paper_leaves_an_existing_paper_unchanged(
    quiz_form: Form,
) -> None:
    existing = served_paper_of([])
    progress = FormProgressFactory(form=quiz_form, served_paper=existing)

    ensure_served_paper(progress)

    assert FormProgress.objects.get(pk=progress.pk).served_paper == existing


@pytest.mark.django_db
def test_ensure_served_paper_keeps_the_first_paper_when_two_requests_race(
    quiz_form: Form,
) -> None:
    progress = FormProgressFactory(form=quiz_form)
    first = FormProgress.objects.get(pk=progress.pk)
    second = FormProgress.objects.get(pk=progress.pk)

    ensure_served_paper(first)
    ensure_served_paper(second)

    stored = FormProgress.objects.get(pk=progress.pk).served_paper
    assert first.served_paper == stored
    assert second.served_paper == stored


@pytest.mark.django_db
def test_ensure_served_paper_does_not_touch_last_updated_time(
    quiz_form: Form,
) -> None:
    progress = FormProgressFactory(form=quiz_form)
    FormProgress.objects.filter(pk=progress.pk).update(
        last_updated_time=timezone.now() - timedelta(days=3)
    )
    progress.refresh_from_db()
    before = progress.last_updated_time

    ensure_served_paper(progress)

    assert FormProgress.objects.get(pk=progress.pk).last_updated_time == before


@pytest.mark.django_db
def test_served_child_ids_holds_every_child_from_every_page_as_uuids(
    quiz_form: Form,
) -> None:
    page_one, page_two = quiz_form.pages.all()
    content = page_one.text_items.get()
    question = page_one.questions.get()
    unanswerable = page_two.questions.get()
    paper = served_paper_of(
        [(page_two, [unanswerable]), (page_one, [content, question])]
    )

    assert served_child_ids(paper) == frozenset(
        {content.id, question.id, unanswerable.id}
    )
