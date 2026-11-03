"""The evaluator that says which pages, questions and content a sitting is asked."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import pytest

from django.utils import timezone

from freedom_ls.form_engine.conditions import (
    answers_by_question,
    compute_path,
    current_path,
    sitting_path,
)
from freedom_ls.form_engine.factories import (
    FormContentFactory,
    FormFactory,
    FormPageFactory,
    FormProgressFactory,
    FormQuestionFactory,
    QuestionAnswerFactory,
    QuestionOptionFactory,
)
from freedom_ls.form_engine.models import (
    Form,
    FormContent,
    FormPage,
    FormProgress,
    FormQuestion,
    QuestionOption,
)

pytestmark = pytest.mark.django_db


@dataclass
class BranchingForm:
    form: Form
    page_one: FormPage
    page_two: FormPage
    page_three: FormPage
    choice: FormQuestion
    yes: QuestionOption
    no: QuestionOption
    boxes: FormQuestion
    box_a: QuestionOption
    box_b: QuestionOption
    gated_one: FormQuestion
    gated_two: FormQuestion
    gated_content: FormContent
    page_three_question: FormQuestion


@pytest.fixture
def branching_form(mock_site_context) -> BranchingForm:
    """Page 2 opens on `yes`; page 3's one question opens on checkbox `a`."""
    form: Form = FormFactory()
    page_one = FormPageFactory(form=form, order=0)
    choice = FormQuestionFactory(form_page=page_one, type="multiple_choice", order=0)
    yes = QuestionOptionFactory(question=choice, value="yes", order=0)
    no = QuestionOptionFactory(question=choice, value="no", order=1)
    boxes = FormQuestionFactory(form_page=page_one, type="checkboxes", order=1)
    box_a = QuestionOptionFactory(question=boxes, value="a", order=0)
    box_b = QuestionOptionFactory(question=boxes, value="b", order=1)

    page_two = FormPageFactory(form=form, order=1, condition_option=yes)
    gated_content = FormContentFactory(form_page=page_two, order=0)
    gated_one = FormQuestionFactory(form_page=page_two, type="short_text", order=1)
    gated_two = FormQuestionFactory(form_page=page_two, type="short_text", order=2)

    page_three = FormPageFactory(form=form, order=2)
    page_three_question = FormQuestionFactory(
        form_page=page_three,
        type="short_text",
        order=0,
        condition_option=box_a,
    )
    return BranchingForm(
        form=form,
        page_one=page_one,
        page_two=page_two,
        page_three=page_three,
        choice=choice,
        yes=yes,
        no=no,
        boxes=boxes,
        box_a=box_a,
        box_b=box_b,
        gated_one=gated_one,
        gated_two=gated_two,
        gated_content=gated_content,
        page_three_question=page_three_question,
    )


def _select(
    form_progress: FormProgress, question: FormQuestion, *options: QuestionOption
) -> None:
    answer = QuestionAnswerFactory(form_progress=form_progress, question=question)
    answer.selected_options.set(options)


def _fresh(form: Form) -> Form:
    """The form as a new request would load it, with no prefetches cached."""
    fresh: Form = Form.objects.get(pk=form.pk)
    return fresh


def test_no_answers_leaves_gated_pages_and_questions_off_path(
    branching_form: BranchingForm,
) -> None:
    form_progress = FormProgressFactory(form=branching_form.form)

    path = current_path(form_progress)

    assert [number for number, _ in path.numbered_pages()] == [1]
    assert not path.has_question(branching_form.gated_one.id)
    assert not path.has_question(branching_form.page_three_question.id)


def test_selecting_the_gate_option_puts_the_page_on_path_and_numbers_by_position(
    branching_form: BranchingForm,
) -> None:
    form_progress = FormProgressFactory(form=branching_form.form)
    _select(form_progress, branching_form.choice, branching_form.yes)
    _select(form_progress, branching_form.boxes, branching_form.box_a)

    path = current_path(form_progress)

    assert path.page_position(2) == 2
    assert path.page_position(3) == 3


def test_selecting_the_other_option_skips_the_gated_page(
    branching_form: BranchingForm,
) -> None:
    form_progress = FormProgressFactory(form=branching_form.form)
    _select(form_progress, branching_form.choice, branching_form.no)
    _select(form_progress, branching_form.boxes, branching_form.box_a)

    path = current_path(form_progress)

    assert not path.has_page_number(2)
    assert path.landing_page_number(2) == 3
    assert path.next_page_number(1) == 3
    assert path.previous_page_number(3) == 1
    assert path.page_position(3) == 2


def test_landing_on_a_page_past_the_last_on_path_page_goes_to_the_last(
    branching_form: BranchingForm,
) -> None:
    form_progress = FormProgressFactory(form=branching_form.form)
    _select(form_progress, branching_form.choice, branching_form.yes)

    path = current_path(form_progress)

    assert path.landing_page_number(3) == 2
    assert path.last_page_number() == 2


def test_first_page_number_at_or_after_skips_off_path_pages(
    branching_form: BranchingForm,
) -> None:
    form_progress = FormProgressFactory(form=branching_form.form)

    path = current_path(form_progress)

    assert path.first_page_number_at_or_after(2) is None
    assert path.first_page_number_at_or_after(1) == 1


def test_checkbox_condition_holds_when_option_is_among_several_selected(
    branching_form: BranchingForm,
) -> None:
    form_progress = FormProgressFactory(form=branching_form.form)
    _select(
        form_progress, branching_form.boxes, branching_form.box_a, branching_form.box_b
    )

    path = current_path(form_progress)

    assert path.has_question(branching_form.page_three_question.id)


def test_checkbox_condition_fails_when_option_is_not_selected(
    branching_form: BranchingForm,
) -> None:
    form_progress = FormProgressFactory(form=branching_form.form)
    _select(form_progress, branching_form.boxes, branching_form.box_b)

    path = current_path(form_progress)

    assert not path.has_question(branching_form.page_three_question.id)


def test_a_condition_whose_source_is_off_path_is_false(
    branching_form: BranchingForm,
) -> None:
    follow_up = QuestionOptionFactory(question=branching_form.gated_one, value="x")
    chained = FormQuestionFactory(
        form_page=branching_form.page_three,
        type="short_text",
        order=5,
        condition_option=follow_up,
    )
    form_progress = FormProgressFactory(form=branching_form.form)
    _select(form_progress, branching_form.choice, branching_form.no)
    _select(form_progress, branching_form.gated_one, follow_up)

    path = current_path(form_progress)

    assert not path.has_question(chained.id)


def test_an_open_page_whose_children_are_all_off_path_is_off_path(
    branching_form: BranchingForm,
) -> None:
    page_four = FormPageFactory(form=branching_form.form, order=3)
    FormQuestionFactory(
        form_page=page_four,
        type="short_text",
        order=0,
        condition_option=branching_form.box_b,
    )
    form_progress = FormProgressFactory(form=branching_form.form)

    path = current_path(form_progress)

    assert not path.has_page_number(4)


def test_an_open_page_with_no_children_is_on_path(
    branching_form: BranchingForm,
) -> None:
    FormPageFactory(form=branching_form.form, order=3)
    form_progress = FormProgressFactory(form=branching_form.form)

    path = current_path(form_progress)

    assert path.has_page_number(4)


def test_question_positions_count_only_on_path_questions(
    branching_form: BranchingForm,
) -> None:
    form_progress = FormProgressFactory(form=branching_form.form)
    _select(form_progress, branching_form.choice, branching_form.yes)
    _select(form_progress, branching_form.boxes, branching_form.box_a)

    positions = current_path(form_progress).question_positions()

    assert positions[branching_form.gated_two.id] == 4
    assert positions[branching_form.page_three_question.id] == 5


def test_questions_of_a_page_leave_out_content_blocks(
    branching_form: BranchingForm,
) -> None:
    form_progress = FormProgressFactory(form=branching_form.form)
    _select(form_progress, branching_form.choice, branching_form.yes)

    path = current_path(form_progress)

    assert path.questions_of(branching_form.page_two) == [
        branching_form.gated_one,
        branching_form.gated_two,
    ]
    assert branching_form.gated_content in path.children_of(branching_form.page_two)


def test_as_asked_holds_string_uuids_under_pages_questions_and_content(
    branching_form: BranchingForm,
) -> None:
    form_progress = FormProgressFactory(form=branching_form.form)
    _select(form_progress, branching_form.choice, branching_form.yes)

    asked = current_path(form_progress).as_asked()

    assert asked["pages"] == [
        str(branching_form.page_one.id),
        str(branching_form.page_two.id),
    ]
    assert str(branching_form.gated_one.id) in asked["questions"]
    assert asked["content"] == [str(branching_form.gated_content.id)]
    assert all(isinstance(value, str) for key in asked for value in asked[key])


def test_sitting_path_with_asked_ignores_answers_and_later_condition_edits(
    branching_form: BranchingForm,
) -> None:
    form_progress = FormProgressFactory(form=branching_form.form)
    _select(form_progress, branching_form.choice, branching_form.yes)
    form_progress.asked = current_path(form_progress).as_asked()
    form_progress.save()
    branching_form.page_two.condition_option = branching_form.no
    branching_form.page_two.save()
    form_progress.answers.all().delete()

    path = sitting_path(FormProgress.objects.get(pk=form_progress.pk))

    assert path.has_page_number(2)
    assert path.has_question(branching_form.gated_one.id)
    assert not path.has_question(branching_form.page_three_question.id)


def test_sitting_path_for_a_completed_sitting_without_asked_is_everything(
    branching_form: BranchingForm,
) -> None:
    form_progress = FormProgressFactory(
        form=branching_form.form, completed_time=timezone.now()
    )

    path = sitting_path(form_progress)

    assert path.page_count == 3
    assert path.has_question(branching_form.page_three_question.id)
    assert path.has_question(branching_form.gated_two.id)


def test_sitting_path_for_an_open_sitting_follows_its_answers(
    branching_form: BranchingForm,
) -> None:
    form_progress = FormProgressFactory(form=branching_form.form)
    _select(form_progress, branching_form.choice, branching_form.yes)

    path = sitting_path(form_progress)

    assert path.has_page_number(2)
    assert not path.has_page_number(3)


def test_compute_path_uses_the_answers_it_is_given(
    branching_form: BranchingForm,
) -> None:
    form_progress = FormProgressFactory(form=branching_form.form)
    _select(form_progress, branching_form.choice, branching_form.yes)
    answers = answers_by_question(form_progress)

    path = compute_path(_fresh(branching_form.form), answers)

    assert path.has_page_number(2)


def test_answers_by_question_is_keyed_by_question_id(
    branching_form: BranchingForm,
) -> None:
    form_progress = FormProgressFactory(form=branching_form.form)
    _select(form_progress, branching_form.choice, branching_form.yes)

    answers = answers_by_question(form_progress)

    assert list(answers) == [branching_form.choice.id]
    assert isinstance(next(iter(answers)), UUID)


def test_compute_path_stays_within_the_query_budget(
    branching_form: BranchingForm, django_assert_max_num_queries
) -> None:
    form_progress = FormProgressFactory(form=branching_form.form)
    _select(form_progress, branching_form.choice, branching_form.yes)
    form_progress = FormProgress.objects.get(pk=form_progress.pk)
    form_progress.form = _fresh(branching_form.form)

    with django_assert_max_num_queries(8):
        current_path(form_progress)


def test_a_second_compute_path_on_the_same_form_adds_only_the_answer_queries(
    branching_form: BranchingForm, django_assert_max_num_queries
) -> None:
    form_progress = FormProgressFactory(form=_fresh(branching_form.form))
    _select(form_progress, branching_form.choice, branching_form.yes)
    current_path(form_progress)

    with django_assert_max_num_queries(2):
        current_path(form_progress)
