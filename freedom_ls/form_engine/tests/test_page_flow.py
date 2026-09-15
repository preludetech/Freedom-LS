"""`page_flow` is the page itself, shared by the exam runner and the application
shell: which page a number names, what a submission of it did, and the context a
template needs to draw it. These pin the parts the two callers must not drift on
-- above all that a refused submission still saves the answers it carried.
"""

from __future__ import annotations

import pytest

from django.http import Http404, QueryDict

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormProgressFactory,
    FormQuestionFactory,
)
from freedom_ls.form_engine.models import Form, FormProgress
from freedom_ls.form_engine.page_flow import (
    PageSubmission,
    page_at,
    page_context,
    resolve_page,
    submit_page,
)


def _post_data(pairs: dict[str, list[str]]) -> QueryDict:
    data = QueryDict(mutable=True)
    for name, values in pairs.items():
        data.setlist(name, values)
    return data


def _url_for_page(number: int) -> str:
    return f"/page/{number}/"


@pytest.fixture
def two_page_form(mock_site_context) -> Form:
    """Two pages. Page one carries a required and an optional short-text
    question; page two carries one required date question.
    """
    form: Form = FormFactory()
    first = FormPageFactory(form=form, order=0, title="Page one")
    FormQuestionFactory(form_page=first, type="short_text", order=0, required=True)
    FormQuestionFactory(form_page=first, type="short_text", order=1, required=False)
    second = FormPageFactory(form=form, order=1, title="Page two")
    FormQuestionFactory(form_page=second, type="date", order=0, required=True)
    return form


@pytest.fixture
def sitting(two_page_form) -> FormProgress:
    form_progress: FormProgress = FormProgressFactory(
        user=UserFactory(), form=two_page_form
    )
    return form_progress


@pytest.mark.django_db
def test_page_at_names_the_page_and_its_questions(two_page_form):
    current = page_at(two_page_form, 1)

    assert current is not None
    assert current.page.title == "Page one"
    assert current.number == 1
    assert current.total_pages == 2
    assert len(current.questions) == 2


@pytest.mark.django_db
@pytest.mark.parametrize("page_number", [0, 3, -1])
def test_page_at_returns_none_for_a_page_the_form_does_not_have(
    two_page_form, page_number
):
    assert page_at(two_page_form, page_number) is None


@pytest.mark.django_db
def test_resolve_page_raises_404_for_a_page_the_form_does_not_have(two_page_form):
    with pytest.raises(Http404):
        resolve_page(two_page_form, 3)


@pytest.mark.django_db
def test_is_last_marks_only_the_final_page(two_page_form):
    assert resolve_page(two_page_form, 1).is_last is False
    assert resolve_page(two_page_form, 2).is_last is True


@pytest.mark.django_db
def test_a_submission_with_no_errors_is_accepted(two_page_form, sitting):
    current = resolve_page(two_page_form, 1)
    required = current.questions[0]

    submission = submit_page(
        current, _post_data({f"question_{required.id}": ["Ohm"]}), sitting
    )

    assert submission.accepted is True
    assert submission.rejected_answers == {}
    assert sitting.answers.count() == 1


@pytest.mark.django_db
def test_a_missing_required_answer_refuses_the_submission(two_page_form, sitting):
    current = resolve_page(two_page_form, 1)

    required = current.questions[0]

    submission = submit_page(current, _post_data({}), sitting)

    assert submission.accepted is False
    assert (
        submission.required_answers_error
        == f"Question {required.question_number()} needs an answer "
        "before you can continue."
    )


@pytest.mark.django_db
def test_a_refused_submission_still_saves_the_answers_it_carried(
    two_page_form, sitting
):
    """The invariant both callers depend on: missing one field must not throw
    away the fields that were filled in.
    """
    current = resolve_page(two_page_form, 1)
    required, optional = current.questions

    submission = submit_page(
        current, _post_data({f"question_{optional.id}": ["Kept"]}), sitting
    )

    assert submission.accepted is False
    answer = sitting.answers.get(question=optional)
    assert answer.text_answer == "Kept"
    assert not sitting.answers.filter(question=required).exists()


@pytest.mark.django_db
def test_an_answer_that_is_not_valid_for_its_type_refuses_the_submission(
    two_page_form, sitting
):
    current = resolve_page(two_page_form, 2)
    date_question = current.questions[0]

    submission = submit_page(
        current, _post_data({f"question_{date_question.id}": ["not a date"]}), sitting
    )

    assert submission.accepted is False
    assert date_question.id in submission.rejected_answers
    assert (
        submission.rejected_answers_error
        == f"Question {date_question.question_number()} needs a valid answer."
    )


@pytest.mark.django_db
def test_require_answers_false_lets_a_blank_required_question_through(
    two_page_form, sitting
):
    """Submit-on-exit finalises the sitting as it stands: a blank required
    question must not trap someone inside the exit dialog.
    """
    current = resolve_page(two_page_form, 1)

    submission = submit_page(current, _post_data({}), sitting, require_answers=False)

    assert submission.accepted is True
    assert submission.required_answers_error == ""


@pytest.mark.django_db
def test_require_answers_false_still_refuses_an_invalid_answer(two_page_form, sitting):
    """An answer that cannot be stored at all would freeze the sitting without
    it, so it refuses even when required answers are not being enforced.
    """
    current = resolve_page(two_page_form, 2)
    date_question = current.questions[0]

    submission = submit_page(
        current,
        _post_data({f"question_{date_question.id}": ["not a date"]}),
        sitting,
        require_answers=False,
    )

    assert submission.accepted is False
    assert submission.rejected_answers_error != ""


@pytest.mark.django_db
def test_a_default_submission_is_accepted(two_page_form):
    """A GET submitted nothing, so nothing was refused."""
    assert PageSubmission().accepted is True


@pytest.mark.django_db
def test_context_names_the_next_page_when_there_is_one(two_page_form, sitting):
    current = resolve_page(two_page_form, 1)

    context = page_context(
        two_page_form, current, sitting, PageSubmission(), _url_for_page
    )

    assert context["has_next_page"] is True
    assert context["next_page_url"] == "/page/2/"
    assert context["previous_page_url"] is None


@pytest.mark.django_db
def test_context_has_no_next_page_on_the_last_page(two_page_form, sitting):
    current = resolve_page(two_page_form, 2)

    context = page_context(
        two_page_form, current, sitting, PageSubmission(), _url_for_page
    )

    assert context["has_next_page"] is False
    assert context["next_page_url"] is None
    assert context["previous_page_url"] == "/page/1/"


@pytest.mark.django_db
def test_context_is_editable_unless_the_caller_says_otherwise(two_page_form, sitting):
    current = resolve_page(two_page_form, 1)

    editable = page_context(
        two_page_form, current, sitting, PageSubmission(), _url_for_page
    )
    locked = page_context(
        two_page_form,
        current,
        sitting,
        PageSubmission(),
        _url_for_page,
        read_only=True,
    )

    assert editable["read_only"] is False
    assert locked["read_only"] is True


@pytest.mark.django_db
def test_context_carries_the_submission_errors(two_page_form, sitting):
    current = resolve_page(two_page_form, 1)
    submission = submit_page(current, _post_data({}), sitting)

    context = page_context(two_page_form, current, sitting, submission, _url_for_page)

    assert context["required_answers_error"] == submission.required_answers_error
    assert context["rejected_answers"] == submission.rejected_answers
    assert context["rejected_answers_error"] == submission.rejected_answers_error
