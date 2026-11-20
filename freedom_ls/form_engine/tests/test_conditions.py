"""The evaluator that says which pages, questions and content a sitting is asked."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import pytest

from django.utils import timezone

from freedom_ls.form_engine.conditions import (
    ServedPaper,
    answers_by_question,
    compute_path,
    current_path,
    served_path,
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
    served_paper_of,
)
from freedom_ls.form_engine.models import (
    Form,
    FormContent,
    FormPage,
    FormProgress,
    FormQuestion,
    QuestionOption,
)
from freedom_ls.form_engine.served_paper import build_served_paper

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


@dataclass
class ServedForm:
    """Three authored pages: page one holds a question and a content block,
    page two two questions, page three one question."""

    form: Form
    page_one: FormPage
    page_two: FormPage
    page_three: FormPage
    q_one: FormQuestion
    one_a: QuestionOption
    one_b: QuestionOption
    one_c: QuestionOption
    content: FormContent
    q_two: FormQuestion
    q_three: FormQuestion
    q_four: FormQuestion


@pytest.fixture
def served_form(mock_site_context: object) -> ServedForm:
    form: Form = FormFactory()
    page_one = FormPageFactory(form=form, order=0)
    q_one = FormQuestionFactory(form_page=page_one, type="multiple_choice", order=0)
    one_a = QuestionOptionFactory(question=q_one, value="a", order=0)
    one_b = QuestionOptionFactory(question=q_one, value="b", order=1)
    one_c = QuestionOptionFactory(question=q_one, value="c", order=2)
    content = FormContentFactory(form_page=page_one, order=1)
    page_two = FormPageFactory(form=form, order=1)
    q_two = FormQuestionFactory(form_page=page_two, type="short_text", order=0)
    q_three = FormQuestionFactory(form_page=page_two, type="short_text", order=1)
    page_three = FormPageFactory(form=form, order=2)
    q_four = FormQuestionFactory(form_page=page_three, type="short_text", order=0)
    return ServedForm(
        form=form,
        page_one=page_one,
        page_two=page_two,
        page_three=page_three,
        q_one=q_one,
        one_a=one_a,
        one_b=one_b,
        one_c=one_c,
        content=content,
        q_two=q_two,
        q_three=q_three,
        q_four=q_four,
    )


def _reordered_paper(sf: ServedForm) -> ServedPaper:
    """Pages three, one, two; page two's questions swapped; question one's
    options c, a, b."""
    return served_paper_of(
        [
            (sf.page_three, [sf.q_four]),
            (sf.page_one, [sf.content, sf.q_one]),
            (sf.page_two, [sf.q_three, sf.q_two]),
        ],
        {sf.q_one: [sf.one_c, sf.one_a, sf.one_b]},
    )


def test_served_path_of_a_built_paper_is_the_authored_path(
    served_form: ServedForm,
) -> None:
    paper = build_served_paper(_fresh(served_form.form))

    path = served_path(_fresh(served_form.form), paper)

    assert [page.id for page in path.pages] == [
        served_form.page_one.id,
        served_form.page_two.id,
        served_form.page_three.id,
    ]
    assert [child.id for child in path.children_of(served_form.page_one)] == [
        served_form.q_one.id,
        served_form.content.id,
    ]
    assert [o.id for o in path.options_of(served_form.q_one)] == [
        served_form.one_a.id,
        served_form.one_b.id,
        served_form.one_c.id,
    ]
    assert path.has_missing_served_items is False


def test_served_path_follows_the_served_page_child_and_option_order(
    served_form: ServedForm,
) -> None:
    sf = served_form

    path = served_path(_fresh(sf.form), _reordered_paper(sf))

    assert [number for number, _ in path.numbered_pages()] == [3, 1, 2]
    assert [page.id for page in path.pages] == [
        sf.page_three.id,
        sf.page_one.id,
        sf.page_two.id,
    ]
    assert [q.id for q in path.questions()] == [
        sf.q_four.id,
        sf.q_one.id,
        sf.q_three.id,
        sf.q_two.id,
    ]
    assert path.question_positions() == {
        sf.q_four.id: 1,
        sf.q_one.id: 2,
        sf.q_three.id: 3,
        sf.q_two.id: 4,
    }
    assert [path.page_position(n) for n in (3, 1, 2)] == [1, 2, 3]
    assert [child.id for child in path.children_of(sf.page_one)] == [
        sf.content.id,
        sf.q_one.id,
    ]
    assert [o.id for o in path.options_of(sf.q_one)] == [
        sf.one_c.id,
        sf.one_a.id,
        sf.one_b.id,
    ]


def test_navigation_over_a_served_order_follows_served_positions(
    served_form: ServedForm,
) -> None:
    path = served_path(_fresh(served_form.form), _reordered_paper(served_form))

    assert path.next_page_number(3) == 1
    assert path.next_page_number(1) == 2
    assert path.next_page_number(2) is None
    assert path.previous_page_number(2) == 1
    assert path.previous_page_number(1) == 3
    assert path.previous_page_number(3) is None
    assert path.first_page_number_at_or_after(2) == 2
    assert path.last_page_number() == 2
    assert path.landing_page_number(1) == 2


def test_a_number_off_a_served_path_lands_on_the_first_greater_number_else_the_last(
    served_form: ServedForm,
) -> None:
    sf = served_form
    paper = served_paper_of([(sf.page_three, [sf.q_four]), (sf.page_one, [sf.q_one])])
    path = served_path(_fresh(sf.form), paper)

    assert path.first_page_number_at_or_after(2) == 3
    assert path.landing_page_number(2) == 3
    assert path.next_page_number(2) == 3
    assert path.previous_page_number(2) == 1
    assert path.landing_page_number(4) == 1


def test_a_served_paper_that_omits_a_page_and_a_question_leaves_them_off_the_path(
    served_form: ServedForm,
) -> None:
    sf = served_form
    paper = served_paper_of(
        [(sf.page_one, [sf.q_one]), (sf.page_two, [sf.q_two])],
    )

    path = served_path(_fresh(sf.form), paper)

    assert [number for number, _ in path.numbered_pages()] == [1, 2]
    assert not path.has_question(sf.q_three.id)
    assert not path.has_question(sf.q_four.id)
    assert path.content_ids == frozenset()
    assert path.has_missing_served_items is False


def test_a_deleted_page_is_skipped_and_flagged(served_form: ServedForm) -> None:
    sf = served_form
    paper = build_served_paper(_fresh(sf.form))
    sf.page_two.delete()

    path = served_path(_fresh(sf.form), paper)

    assert [page.id for page in path.pages] == [sf.page_one.id, sf.page_three.id]
    assert path.has_missing_served_items is True


def test_a_deleted_child_is_skipped_and_flagged(served_form: ServedForm) -> None:
    sf = served_form
    paper = build_served_paper(_fresh(sf.form))
    sf.q_three.delete()

    path = served_path(_fresh(sf.form), paper)

    assert [q.id for q in path.questions_of(sf.page_two)] == [sf.q_two.id]
    assert path.has_missing_served_items is True


def test_a_deleted_option_is_skipped_and_flagged(served_form: ServedForm) -> None:
    sf = served_form
    paper = build_served_paper(_fresh(sf.form))
    sf.one_b.delete()

    path = served_path(_fresh(sf.form), paper)

    assert [o.id for o in path.options_of(sf.q_one)] == [sf.one_a.id, sf.one_c.id]
    assert path.has_missing_served_items is True


def test_a_question_whose_served_options_are_all_gone_shows_its_live_options(
    served_form: ServedForm,
) -> None:
    sf = served_form
    paper = build_served_paper(_fresh(sf.form))
    for option in (sf.one_a, sf.one_b, sf.one_c):
        option.delete()
    new_y = QuestionOptionFactory(question=sf.q_one, value="y", order=1)
    new_x = QuestionOptionFactory(question=sf.q_one, value="x", order=0)

    path = served_path(_fresh(sf.form), paper)

    assert [o.id for o in path.options_of(sf.q_one)] == [new_x.id, new_y.id]
    assert path.has_missing_served_items is True


def test_a_question_served_with_no_options_shows_the_options_it_gained(
    served_form: ServedForm,
) -> None:
    sf = served_form
    paper = build_served_paper(_fresh(sf.form))
    gained = QuestionOptionFactory(question=sf.q_two, value="gained", order=0)

    path = served_path(_fresh(sf.form), paper)

    assert [o.id for o in path.options_of(sf.q_two)] == [gained.id]
    assert path.has_missing_served_items is False


def test_an_option_added_beside_surviving_served_options_is_not_shown(
    served_form: ServedForm,
) -> None:
    sf = served_form
    paper = build_served_paper(_fresh(sf.form))
    QuestionOptionFactory(question=sf.q_one, value="d", order=3)

    path = served_path(_fresh(sf.form), paper)

    assert [o.id for o in path.options_of(sf.q_one)] == [
        sf.one_a.id,
        sf.one_b.id,
        sf.one_c.id,
    ]


def test_a_served_page_whose_children_are_all_gone_is_skipped(
    served_form: ServedForm,
) -> None:
    sf = served_form
    paper = build_served_paper(_fresh(sf.form))
    sf.q_four.delete()

    path = served_path(_fresh(sf.form), paper)

    assert [page.id for page in path.pages] == [sf.page_one.id, sf.page_two.id]


def test_a_page_that_was_empty_when_served_is_kept(served_form: ServedForm) -> None:
    sf = served_form
    empty_page = FormPageFactory(form=sf.form, order=3)
    paper = build_served_paper(_fresh(sf.form))

    path = served_path(_fresh(sf.form), paper)

    assert [page.id for page in path.pages][-1] == empty_page.id
    assert path.children_of(empty_page) == []
    assert path.has_missing_served_items is False


def test_a_question_moved_to_another_form_is_skipped(served_form: ServedForm) -> None:
    sf = served_form
    paper = build_served_paper(_fresh(sf.form))
    sf.q_three.form_page = FormPageFactory(form=FormFactory(), order=0)
    sf.q_three.save()

    path = served_path(_fresh(sf.form), paper)

    assert not path.has_question(sf.q_three.id)
    assert path.has_missing_served_items is True


def test_a_question_moved_to_another_page_of_the_form_stays_under_its_served_page(
    served_form: ServedForm,
) -> None:
    sf = served_form
    paper = build_served_paper(_fresh(sf.form))
    sf.q_three.form_page = sf.page_three
    sf.q_three.save()

    path = served_path(_fresh(sf.form), paper)

    assert [q.id for q in path.questions_of(sf.page_two)] == [
        sf.q_two.id,
        sf.q_three.id,
    ]
    assert [q.id for q in path.questions_of(sf.page_three)] == [sf.q_four.id]
    assert path.has_missing_served_items is False


def test_reached_position_of_a_number_on_the_path_is_its_position(
    served_form: ServedForm,
) -> None:
    path = served_path(_fresh(served_form.form), _reordered_paper(served_form))

    assert path.reached_position(3) == 1
    assert path.reached_position(2) == 3


def test_reached_position_of_a_number_off_the_path_counts_the_pages_before_its_landing(
    served_form: ServedForm,
) -> None:
    sf = served_form
    paper = served_paper_of([(sf.page_one, [sf.q_one]), (sf.page_three, [sf.q_four])])
    path = served_path(_fresh(sf.form), paper)

    assert path.reached_position(2) == 1
    assert path.reached_position(0) == 0
    assert path.reached_position(9) == 2


def test_options_of_a_path_with_no_served_paper_is_the_option_order(
    served_form: ServedForm,
) -> None:
    path = compute_path(_fresh(served_form.form), {})
    question = path.questions()[0]

    options = path.options_of(question)

    assert [o.id for o in options] == [
        served_form.one_a.id,
        served_form.one_b.id,
        served_form.one_c.id,
    ]


def _served_form_of_size(question_count: int) -> tuple[Form, ServedPaper]:
    form: Form = FormFactory()
    page = FormPageFactory(form=form, order=0)
    for order in range(question_count):
        question = FormQuestionFactory(
            form_page=page, type="multiple_choice", order=order
        )
        QuestionOptionFactory(question=question, value="a", order=0)
        QuestionOptionFactory(question=question, value="b", order=1)
    return _fresh(form), build_served_paper(_fresh(form))


def test_served_path_stays_within_a_query_bound_as_the_questions_grow(
    mock_site_context, django_assert_max_num_queries
) -> None:
    form, paper = _served_form_of_size(12)

    with django_assert_max_num_queries(8):
        served_path(form, paper)


def test_sitting_path_reads_the_served_paper_before_asked(
    served_form: ServedForm,
) -> None:
    sf = served_form
    form_progress = FormProgressFactory(
        form=sf.form,
        served_paper=_reordered_paper(sf),
        asked=_full_asked(sf),
    )

    path = sitting_path(FormProgress.objects.get(pk=form_progress.pk))

    assert [number for number, _ in path.numbered_pages()] == [3, 1, 2]


def _full_asked(sf: ServedForm) -> dict[str, list[str]]:
    return {
        "pages": [str(sf.page_one.id)],
        "questions": [str(sf.q_one.id)],
        "content": [],
    }


def test_current_path_reads_the_served_paper(served_form: ServedForm) -> None:
    form_progress = FormProgressFactory(
        form=served_form.form, served_paper=_reordered_paper(served_form)
    )

    path = current_path(FormProgress.objects.get(pk=form_progress.pk))

    assert [number for number, _ in path.numbered_pages()] == [3, 1, 2]


def test_current_path_and_sitting_path_without_a_served_paper_are_the_computed_path(
    branching_form: BranchingForm,
) -> None:
    form_progress = FormProgressFactory(form=branching_form.form)
    _select(form_progress, branching_form.choice, branching_form.yes)
    reloaded = FormProgress.objects.get(pk=form_progress.pk)

    current = current_path(reloaded)
    sitting = sitting_path(reloaded)

    assert [number for number, _ in current.numbered_pages()] == [1, 2]
    assert [number for number, _ in sitting.numbered_pages()] == [1, 2]
    assert current.options_of(branching_form.choice) == list(
        branching_form.choice.options.all()
    )
