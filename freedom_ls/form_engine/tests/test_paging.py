"""Paging is the arithmetic both the exam runner and the application shell do to
decide which page a sitting resumes on, which pages the page-jump nav may reach,
and which required questions are still outstanding. It lives here so neither
caller owns it and the two cannot drift apart.
"""

from __future__ import annotations

import pytest

from django.http import QueryDict

from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormProgressFactory,
    FormQuestionFactory,
    QuestionAnswerFactory,
    QuestionOptionFactory,
)
from freedom_ls.form_engine.models import Form, FormProgress, FormQuestion
from freedom_ls.form_engine.paging import (
    answered_counts,
    build_page_links,
    page_accessibility_limit,
    resume_page_number,
    unanswered_required_in_form,
    unanswered_required_message,
    unanswered_required_on_page,
)


def _post_data(pairs: dict[str, list[str]]) -> QueryDict:
    data = QueryDict(mutable=True)
    for name, values in pairs.items():
        data.setlist(name, values)
    return data


@pytest.fixture
def four_page_form(mock_site_context) -> Form:
    """Four pages, one short-text question each. Page 2's is optional."""
    form: Form = FormFactory()
    for order in range(4):
        page = FormPageFactory(form=form, order=order, title=f"Page {order + 1}")
        FormQuestionFactory(
            form_page=page, type="short_text", order=0, required=order != 1
        )
    return form


def _question_on_page(form: Form, page_number: int) -> FormQuestion:
    page = list(form.pages.all())[page_number - 1]
    question: FormQuestion = page.questions.first()
    return question


def _answer(form_progress: FormProgress, question: FormQuestion) -> None:
    QuestionAnswerFactory(
        form_progress=form_progress, question=question, text_answer="something"
    )


@pytest.mark.django_db
def test_resume_page_is_the_furthest_page_answered_not_the_first_gap(
    mock_site_context, four_page_form
):
    form_progress = FormProgressFactory(form=four_page_form)
    _answer(form_progress, _question_on_page(four_page_form, 1))
    _answer(form_progress, _question_on_page(four_page_form, 3))
    _answer(form_progress, _question_on_page(four_page_form, 4))

    assert resume_page_number(form_progress) == 4


@pytest.mark.django_db
def test_page_accessibility_limit_takes_the_current_page_when_it_is_further(
    mock_site_context, four_page_form
):
    form_progress = FormProgressFactory(form=four_page_form)

    assert page_accessibility_limit(form_progress, current_page_number=3) == 3


@pytest.mark.django_db
def test_page_accessibility_limit_takes_the_resume_page_when_it_is_further(
    mock_site_context, four_page_form
):
    form_progress = FormProgressFactory(form=four_page_form)
    _answer(form_progress, _question_on_page(four_page_form, 4))

    assert page_accessibility_limit(form_progress, current_page_number=1) == 4


@pytest.mark.django_db
def test_unanswered_required_in_form_names_questions_on_unvisited_pages(
    mock_site_context, four_page_form
):
    form_progress = FormProgressFactory(form=four_page_form)
    _answer(form_progress, _question_on_page(four_page_form, 1))
    _answer(form_progress, _question_on_page(four_page_form, 4))

    outstanding = unanswered_required_in_form(form_progress)

    assert outstanding == [_question_on_page(four_page_form, 3)]


@pytest.mark.django_db
def test_unanswered_required_on_the_last_page_finds_nothing_when_it_is_answered(
    mock_site_context, four_page_form
):
    form_progress = FormProgressFactory(form=four_page_form)
    question = _question_on_page(four_page_form, 4)

    outstanding = unanswered_required_on_page(
        [question], _post_data({f"question_{question.id}": ["yes"]}), form_progress
    )

    assert outstanding == []


@pytest.mark.django_db
def test_required_file_question_with_no_stored_row_is_outstanding(mock_site_context):
    form = FormFactory()
    page = FormPageFactory(form=form, order=0)
    question: FormQuestion = FormQuestionFactory(
        form_page=page, type="file_upload", order=0, required=True
    )
    form_progress = FormProgressFactory(form=form)

    outstanding = unanswered_required_on_page([question], _post_data({}), form_progress)

    assert outstanding == [question]


@pytest.mark.django_db
def test_required_file_question_with_a_stored_row_is_answered(mock_site_context):
    form = FormFactory()
    page = FormPageFactory(form=form, order=0)
    question: FormQuestion = FormQuestionFactory(
        form_page=page, type="file_upload", order=0, required=True
    )
    form_progress = FormProgressFactory(form=form)
    QuestionAnswerFactory(form_progress=form_progress, question=question)

    outstanding = unanswered_required_on_page([question], _post_data({}), form_progress)

    assert outstanding == []


@pytest.mark.django_db
def test_build_page_links_marks_the_current_page_and_the_reachable_ones(
    mock_site_context, four_page_form
):
    form_progress = FormProgressFactory(form=four_page_form)

    links = build_page_links(
        four_page_form, form_progress, 2, lambda number: f"/page/{number}/"
    )

    assert links == [
        {
            "number": 1,
            "title": "Page 1",
            "url": "/page/1/",
            "is_current": False,
            "is_accessible": True,
        },
        {
            "number": 2,
            "title": "Page 2",
            "url": "/page/2/",
            "is_current": True,
            "is_accessible": True,
        },
        {
            "number": 3,
            "title": "Page 3",
            "url": "/page/3/",
            "is_current": False,
            "is_accessible": False,
        },
        {
            "number": 4,
            "title": "Page 4",
            "url": "/page/4/",
            "is_current": False,
            "is_accessible": False,
        },
    ]


@pytest.mark.django_db
def test_answered_counts_exclude_the_current_page_from_the_other_pages_tally(
    mock_site_context, four_page_form
):
    form_progress = FormProgressFactory(form=four_page_form)
    _answer(form_progress, _question_on_page(four_page_form, 1))
    _answer(form_progress, _question_on_page(four_page_form, 2))
    current = [_question_on_page(four_page_form, 2)]

    counts = answered_counts(four_page_form, form_progress, current)

    assert counts == {
        "answered_count": 2,
        "answered_other_pages": 1,
        "total_question_count": 4,
    }


@pytest.mark.django_db
def test_one_outstanding_question_is_named_in_the_singular(
    mock_site_context, four_page_form
):
    question = _question_on_page(four_page_form, 3)

    assert (
        unanswered_required_message([question])
        == "Question 3 needs an answer before you can continue."
    )


@pytest.mark.django_db
def test_several_outstanding_questions_are_listed_in_the_plural(mock_site_context):
    form = FormFactory()
    page = FormPageFactory(form=form, order=0)
    questions = [
        FormQuestionFactory(form_page=page, type="short_text", order=order)
        for order in range(3)
    ]

    assert (
        unanswered_required_message(questions)
        == "Questions 1, 2 and 3 need answers before you can continue."
    )


@pytest.mark.django_db
def test_choice_answers_survive_the_existing_answers_lookup(mock_site_context):
    """`existing_answers_dict` is the check-your-answers page's one read of the
    stored answers, so it has to return the row for each question it is given.
    """
    form = FormFactory()
    page = FormPageFactory(form=form, order=0)
    question = FormQuestionFactory(form_page=page, type="multiple_choice", order=0)
    option = QuestionOptionFactory(question=question, text="Alpha", order=0)
    form_progress = FormProgressFactory(form=form)
    answer = QuestionAnswerFactory(form_progress=form_progress, question=question)
    answer.selected_options.set([option])

    existing = form_progress.existing_answers_dict([question])

    assert list(existing[question.id].selected_options.all()) == [option]


@pytest.mark.django_db
def test_resume_page_is_the_furthest_page_reached_when_nothing_on_it_is_answered(
    mock_site_context, four_page_form
):
    """Reaching a page and leaving before answering it must not drop the
    candidate back in front of the page they had already finished."""
    form_progress = FormProgressFactory(form=four_page_form)
    _answer(form_progress, _question_on_page(four_page_form, 1))
    form_progress.record_page_reached(2)

    assert resume_page_number(form_progress) == 2


@pytest.mark.django_db
def test_page_accessibility_limit_keeps_a_reached_page_after_stepping_back(
    mock_site_context, four_page_form
):
    form_progress = FormProgressFactory(form=four_page_form)
    form_progress.record_page_reached(3)

    assert page_accessibility_limit(form_progress, current_page_number=1) == 3


@pytest.mark.django_db
def test_page_links_keep_a_reached_page_clickable_after_stepping_back(
    mock_site_context, four_page_form
):
    form_progress = FormProgressFactory(form=four_page_form)
    form_progress.record_page_reached(2)

    links = build_page_links(
        four_page_form, form_progress, current_page_number=1, url_for_page=str
    )

    assert [link["is_accessible"] for link in links] == [True, True, False, False]


@pytest.mark.django_db
def test_resume_page_is_clamped_to_the_pages_the_form_still_has(
    mock_site_context, four_page_form
):
    """The reached-page record outlives a page an author deletes afterwards;
    resuming on it would be a permanent 404."""
    form_progress = FormProgressFactory(form=four_page_form)
    form_progress.record_page_reached(4)
    four_page_form.pages.filter(order__gte=2).delete()

    assert resume_page_number(form_progress) == 2
    links = build_page_links(
        four_page_form, form_progress, current_page_number=1, url_for_page=str
    )
    assert [link["is_accessible"] for link in links] == [True, True]
