from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import pytest
from pytest_django.fixtures import DjangoAssertNumQueries

from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import ProtectedError, RestrictedError
from django.test import override_settings

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.form_engine.conditions import answers_by_question, current_path
from freedom_ls.form_engine.factories import (
    FormContentFactory,
    FormDeclarationFactory,
    FormFactory,
    FormPageFactory,
    FormProgressFactory,
    FormQuestionFactory,
    QuestionAnswerFactory,
    QuestionAnswerFileFactory,
    QuestionOptionFactory,
    served_paper_of,
)
from freedom_ls.form_engine.models import (
    Form,
    FormContent,
    FormDeclaration,
    FormPage,
    FormProgress,
    FormQuestion,
    FormStrategy,
    QuestionAnswerFile,
    QuestionOption,
    question_answer_file_upload_to,
)
from freedom_ls.form_engine.signals import form_attempt_completed
from freedom_ls.tests.factories import SiteFactory
from freedom_ls.tests.retire import retire
from freedom_ls.tests.site_context import site_context

# QuestionAnswer.question is PROTECTed against FormQuestion deletion.


@pytest.mark.django_db
def test_deleting_a_form_question_with_an_answer_is_blocked(mock_site_context):
    answer = QuestionAnswerFactory()

    with pytest.raises(ProtectedError), transaction.atomic():
        answer.question.delete()


# A stored answer file is PII. Its key is namespaced by the applicant so an
# erasure request has a prefix to sweep, and nothing may abandon an object in the
# bucket: removing an answer, deleting the applicant, or replacing the file all
# have to take the old object with them.


@pytest.fixture
def answer_file(mock_site_context) -> QuestionAnswerFile:
    answer_file: QuestionAnswerFile = QuestionAnswerFileFactory()
    return answer_file


@pytest.mark.django_db
def test_the_stored_key_is_namespaced_by_the_applicant(mock_site_context, answer_file):
    user_id = answer_file.answer.form_progress.user_id

    assert answer_file.file.name.startswith(f"user_uploads/{user_id}/form_answers/")


@pytest.mark.django_db
def test_the_key_takes_its_extension_from_the_name_fls_chose(
    mock_site_context, answer_file
):
    """The applicant's own filename never reaches a storage key."""
    key = question_answer_file_upload_to(answer_file, "file.pdf")

    assert key.endswith(f"{answer_file.pk}.pdf")


@pytest.mark.django_db
def test_removing_the_answer_deletes_the_stored_object(
    mock_site_context, answer_file, django_capture_on_commit_callbacks
):
    storage, name = answer_file.file.storage, answer_file.file.name
    answer = answer_file.answer

    with django_capture_on_commit_callbacks(execute=True):
        answer.delete()

    assert storage.exists(name) is False


@pytest.mark.django_db
def test_removing_the_answer_deletes_the_answer_row(mock_site_context, answer_file):
    answer = answer_file.answer

    answer.delete()

    assert QuestionAnswerFile.objects.filter(pk=answer_file.pk).exists() is False


@pytest.mark.django_db
def test_deleting_the_applicant_deletes_the_stored_object(
    mock_site_context, answer_file, django_capture_on_commit_callbacks
):
    storage, name = answer_file.file.storage, answer_file.file.name

    with django_capture_on_commit_callbacks(execute=True):
        answer_file.answer.form_progress.user.delete()

    assert storage.exists(name) is False


@pytest.mark.django_db
def test_replacing_a_jpg_with_a_pdf_leaves_one_object_behind(
    mock_site_context, answer_file
):
    storage, original = answer_file.file.storage, answer_file.file.name

    answer_file.file.save("file.pdf", ContentFile(b"%PDF-1.4\n"), save=True)

    assert storage.exists(original) is False


@pytest.mark.django_db
def test_replacing_a_jpg_with_another_jpg_leaves_one_object_behind(
    mock_site_context, answer_file
):
    """user_uploads never overwrites, so the replacement lands at a suffixed
    sibling key rather than on top of the old object. The sweep is what stops
    the old one being abandoned in the bucket.
    """
    storage, original = answer_file.file.storage, answer_file.file.name

    answer_file.file.save("file.jpg", ContentFile(b"replacement"), save=True)

    assert storage.exists(original) is False


@pytest.mark.django_db
def test_a_file_belongs_to_exactly_one_answer(mock_site_context):
    page = FormPageFactory(order=0)
    form_progress = FormProgressFactory(form=page.form, user=UserFactory())
    answer = QuestionAnswerFactory(form_progress=form_progress)
    QuestionAnswerFileFactory(answer=answer)

    assert answer.answer_file is not None


# Tests for which page a FormProgress attempt resumes on.


def _page_with_question(form: Form, order: int) -> tuple[FormPage, FormQuestion]:
    """One page carrying a single short-text question."""
    page: FormPage = FormPageFactory(form=form, title=f"Page {order + 1}", order=order)
    question: FormQuestion = FormQuestionFactory(
        form_page=page, question=f"Question {order + 1}", type="short_text", order=0
    )
    return page, question


def _current_page_number(form_progress: FormProgress) -> int:
    answered_ids = set(form_progress.answers.values_list("question_id", flat=True))
    return form_progress.get_current_page_number(
        current_path(form_progress), answered_ids
    )


@pytest.mark.django_db
def test_get_current_page_number_no_answers(mock_site_context):
    """An attempt with nothing answered resumes on the first page."""
    form = FormFactory()
    _page_with_question(form, order=0)
    _page_with_question(form, order=1)

    form_progress: FormProgress = FormProgressFactory(user=UserFactory(), form=form)

    assert _current_page_number(form_progress) == 1


@pytest.mark.django_db
def test_get_current_page_number_partially_answered(mock_site_context):
    """An attempt resumes on the first page still holding an unanswered question."""
    form = FormFactory()
    _page, question_1 = _page_with_question(form, order=0)
    _page_with_question(form, order=1)
    _page_with_question(form, order=2)

    form_progress: FormProgress = FormProgressFactory(user=UserFactory(), form=form)
    QuestionAnswerFactory(
        form_progress=form_progress, question=question_1, text_answer="Answer 1"
    )

    assert _current_page_number(form_progress) == 2


@pytest.mark.django_db
def test_get_current_page_number_all_answered(mock_site_context):
    """With every question answered, the attempt resumes on the last page."""
    form = FormFactory()
    _page_1, question_1 = _page_with_question(form, order=0)
    _page_2, question_2 = _page_with_question(form, order=1)

    form_progress: FormProgress = FormProgressFactory(user=UserFactory(), form=form)
    QuestionAnswerFactory(
        form_progress=form_progress, question=question_1, text_answer="Answer 1"
    )
    QuestionAnswerFactory(
        form_progress=form_progress, question=question_2, text_answer="Answer 2"
    )

    assert _current_page_number(form_progress) == 2


@pytest.mark.django_db
def test_get_current_page_number_page_with_text_only(mock_site_context):
    """A page carrying only content has nothing to answer, so it is not resumed on."""
    form = FormFactory()
    text_only_page = FormPageFactory(form=form, title="Page 1", order=0)
    FormContentFactory(form_page=text_only_page, content="Intro text", order=0)
    _page_with_question(form, order=1)

    form_progress: FormProgress = FormProgressFactory(user=UserFactory(), form=form)

    assert _current_page_number(form_progress) == 2


@pytest.mark.django_db
def test_get_current_page_number_skips_an_off_path_pages_unanswered_question(
    mock_site_context,
):
    """A page the answers have closed is not somewhere the attempt can be stuck."""
    form = FormFactory()
    page_one = FormPageFactory(form=form, order=0)
    choice = FormQuestionFactory(form_page=page_one, type="multiple_choice", order=0)
    yes = QuestionOptionFactory(question=choice, value="yes", order=0)
    no = QuestionOptionFactory(question=choice, value="no", order=1)
    page_two = FormPageFactory(form=form, order=1, condition_option=yes)
    FormQuestionFactory(form_page=page_two, type="short_text", order=0)
    page_three = FormPageFactory(form=form, order=2)
    FormQuestionFactory(form_page=page_three, type="short_text", order=0)
    form_progress: FormProgress = FormProgressFactory(user=UserFactory(), form=form)
    answer = QuestionAnswerFactory(
        form_progress=form_progress, question=choice, text_answer=""
    )
    answer.selected_options.set([no])

    assert _current_page_number(form_progress) == 3


@pytest.mark.django_db
def test_record_page_reached_remembers_the_furthest_page(mock_site_context):
    form: Form = FormFactory()
    pages = [FormPageFactory(form=form, order=order) for order in range(3)]
    form_progress: FormProgress = FormProgressFactory(form=form)
    form_progress.record_page_reached(3, current_path(form_progress))

    form_progress.record_page_reached(1, current_path(form_progress))

    form_progress.refresh_from_db()
    assert form_progress.furthest_page == pages[2]


@pytest.fixture
def served_out_of_order(mock_site_context: object) -> FormProgress:
    """A quiz sitting served its three pages as 3, 1, 2."""
    form: Form = FormFactory(strategy=FormStrategy.QUIZ)
    pages: list[FormPage] = [
        FormPageFactory(form=form, order=order) for order in range(3)
    ]
    progress: FormProgress = FormProgressFactory(form=form)
    progress.served_paper = served_paper_of(
        [(pages[2], []), (pages[0], []), (pages[1], [])]
    )
    progress.save()
    return progress


@pytest.mark.django_db
def test_record_page_reached_moves_forward_by_served_position(served_out_of_order):
    served_out_of_order.record_page_reached(3, current_path(served_out_of_order))

    served_out_of_order.record_page_reached(1, current_path(served_out_of_order))

    served_out_of_order.refresh_from_db()
    assert served_out_of_order.furthest_page.order == 0


@pytest.mark.django_db
def test_record_page_reached_does_not_step_back_in_served_order(served_out_of_order):
    served_out_of_order.record_page_reached(2, current_path(served_out_of_order))

    served_out_of_order.record_page_reached(1, current_path(served_out_of_order))

    served_out_of_order.refresh_from_db()
    assert served_out_of_order.furthest_page.order == 1


@pytest.mark.django_db
def test_complete_writes_the_served_paper_of_an_open_quiz_sitting(mock_site_context):
    form: Form = FormFactory(strategy=FormStrategy.QUIZ)
    FormPageFactory(form=form, order=0)
    progress: FormProgress = FormProgressFactory(form=form)

    progress.complete()

    progress.refresh_from_db()
    assert progress.served_paper is not None


@pytest.mark.django_db
def test_complete_writes_no_served_paper_for_a_non_quiz_form(mock_site_context):
    form: Form = FormFactory(strategy=FormStrategy.CATEGORY_VALUE_SUM)
    FormPageFactory(form=form, order=0)
    progress: FormProgress = FormProgressFactory(form=form)

    progress.complete()

    progress.refresh_from_db()
    assert progress.served_paper is None


@dataclass
class TwoQuestionQuiz:
    form: Form
    first: FormQuestion
    second: FormQuestion
    first_right: QuestionOption
    second_right: QuestionOption
    progress: FormProgress


@pytest.fixture
def two_question_quiz(mock_site_context: object) -> TwoQuestionQuiz:
    """A quiz of two single-option questions; the learner answered the first rightly."""
    form: Form = FormFactory(strategy=FormStrategy.QUIZ, quiz_pass_percentage=100)
    page = FormPageFactory(form=form, order=0)
    first: FormQuestion = FormQuestionFactory(
        form_page=page, type="multiple_choice", order=0
    )
    second: FormQuestion = FormQuestionFactory(
        form_page=page, type="multiple_choice", order=1
    )
    first_right = QuestionOptionFactory(question=first, correct=True, order=0)
    second_right = QuestionOptionFactory(question=second, correct=True, order=0)
    progress: FormProgress = FormProgressFactory(form=form)
    QuestionAnswerFactory(form_progress=progress, question=first).selected_options.add(
        first_right
    )
    return TwoQuestionQuiz(form, first, second, first_right, second_right, progress)


def _serve_only_the_first_question(quiz: TwoQuestionQuiz) -> None:
    page = quiz.first.form_page
    quiz.progress.served_paper = served_paper_of(
        [(page, [quiz.first])], {quiz.first: [quiz.first_right]}
    )
    quiz.progress.save()


@pytest.mark.django_db
def test_a_paper_that_omits_a_question_scores_only_the_served_question(
    two_question_quiz,
):
    _serve_only_the_first_question(two_question_quiz)

    two_question_quiz.progress.complete()

    two_question_quiz.progress.refresh_from_db()
    assert two_question_quiz.progress.scores == {"score": 1, "max_score": 1}


@pytest.mark.django_db
def test_a_paper_that_omits_a_question_makes_the_percentage_and_pass_follow_the_served_one(
    two_question_quiz,
):
    _serve_only_the_first_question(two_question_quiz)
    two_question_quiz.progress.complete()

    two_question_quiz.progress.refresh_from_db()

    assert two_question_quiz.progress.quiz_percentage() == 100
    assert two_question_quiz.progress.passed() is True


@pytest.mark.django_db
def test_a_paper_that_omits_a_question_leaves_it_out_of_the_incorrect_answers(
    two_question_quiz,
):
    _serve_only_the_first_question(two_question_quiz)
    two_question_quiz.progress.complete()

    incorrect = two_question_quiz.progress.get_incorrect_quiz_answers()

    assert incorrect == []


@pytest.mark.django_db
def test_a_served_question_deleted_after_the_paper_was_written_shrinks_max_score(
    two_question_quiz,
):
    two_question_quiz.progress.complete()
    two_question_quiz.progress.refresh_from_db()
    two_question_quiz.second_right.delete()
    two_question_quiz.second.delete()

    scores = two_question_quiz.progress.compute_quiz_scores()

    assert scores == {"score": 1, "max_score": 1}


@pytest.mark.django_db
def test_a_sitting_with_no_paper_scores_over_the_whole_form(two_question_quiz):
    scores = two_question_quiz.progress.compute_quiz_scores()

    assert scores == {"score": 1, "max_score": 2}


@pytest.mark.django_db
def test_complete_scores_the_served_questions_and_still_writes_asked(
    two_question_quiz,
):
    _serve_only_the_first_question(two_question_quiz)

    two_question_quiz.progress.complete()

    two_question_quiz.progress.refresh_from_db()
    assert two_question_quiz.progress.asked is not None
    assert two_question_quiz.progress.asked["questions"] == [
        str(two_question_quiz.first.id)
    ]


# Tests for FormProgress.complete() idempotency.


@pytest.mark.django_db
def test_complete_sets_completed_time(mock_site_context):
    """Completing an attempt stamps it with the time it finished."""
    progress = FormProgressFactory(user=UserFactory(), form=FormFactory())

    progress.complete()

    assert progress.completed_time is not None


@pytest.mark.django_db
def test_complete_twice_does_not_change_completed_time(mock_site_context):
    """Completing an already-completed attempt leaves its finishing time alone."""
    progress = FormProgressFactory(user=UserFactory(), form=FormFactory())
    progress.complete()
    first_completed_time = progress.completed_time

    progress.complete()
    assert progress.completed_time == first_completed_time


@pytest.mark.django_db
def test_complete_twice_does_not_re_score(mock_site_context):
    """Completing an already-completed attempt does not re-score it.

    The stored scores are replaced with a value scoring could never produce, so
    a second run would be visible.
    """
    progress = FormProgressFactory(user=UserFactory(), form=FormFactory())
    progress.complete()
    FormProgress.objects.filter(pk=progress.pk).update(
        scores={"score": 999, "max_score": 999}
    )
    progress.refresh_from_db()

    progress.complete()

    assert progress.scores == {"score": 999, "max_score": 999}


@dataclass
class GatedSitting:
    progress: FormProgress
    gate: FormQuestion
    on_path: FormQuestion
    off_path: FormQuestion


@pytest.fixture
def gated_sitting(mock_site_context) -> GatedSitting:
    """Page 1 asks a yes/no question answered "no"; page 2 is open only on "yes",
    and both pages hold an answered question."""
    form: Form = FormFactory()
    page_one = FormPageFactory(form=form, order=0)
    gate = FormQuestionFactory(form_page=page_one, type="multiple_choice", order=0)
    yes = QuestionOptionFactory(question=gate, value="yes", order=0)
    no = QuestionOptionFactory(question=gate, value="no", order=1)
    on_path = FormQuestionFactory(form_page=page_one, type="short_text", order=1)
    page_two = FormPageFactory(form=form, order=1, condition_option=yes)
    off_path = FormQuestionFactory(form_page=page_two, type="short_text", order=0)
    progress = FormProgressFactory(form=form, user=UserFactory())
    QuestionAnswerFactory(form_progress=progress, question=gate).selected_options.set(
        [no]
    )
    QuestionAnswerFactory(form_progress=progress, question=on_path)
    QuestionAnswerFactory(form_progress=progress, question=off_path)
    return GatedSitting(progress, gate, on_path, off_path)


@pytest.mark.django_db
def test_complete_deletes_the_answers_to_off_path_questions(gated_sitting):
    gated_sitting.progress.complete()

    assert not gated_sitting.progress.answers.filter(
        question=gated_sitting.off_path
    ).exists()


@pytest.mark.django_db
def test_complete_keeps_the_answers_to_on_path_questions(gated_sitting):
    gated_sitting.progress.complete()

    assert set(
        gated_sitting.progress.answers.values_list("question_id", flat=True)
    ) == {
        gated_sitting.gate.id,
        gated_sitting.on_path.id,
    }


@pytest.mark.django_db
def test_complete_keeps_the_answer_to_a_question_moved_to_another_form(
    gated_sitting,
):
    moved = gated_sitting.off_path
    moved.form_page = FormPageFactory(form=FormFactory())
    moved.save()

    gated_sitting.progress.complete()

    assert gated_sitting.progress.answers.filter(question=moved).exists()


@pytest.mark.django_db
def test_complete_records_the_path_the_sitting_was_asked(gated_sitting):
    expected = current_path(gated_sitting.progress).as_asked()

    gated_sitting.progress.complete()

    gated_sitting.progress.refresh_from_db()
    assert gated_sitting.progress.asked == expected


@pytest.mark.django_db
def test_complete_twice_leaves_the_recorded_path_alone(gated_sitting):
    gated_sitting.progress.complete()
    gated_sitting.progress.refresh_from_db()
    recorded = gated_sitting.progress.asked

    gated_sitting.progress.complete()

    gated_sitting.progress.refresh_from_db()
    assert gated_sitting.progress.asked == recorded


@pytest.mark.django_db
def test_form_attempt_completed_is_sent_after_the_row_is_written(gated_sitting):
    seen: list[dict[str, list[str]]] = []

    def _read_stored_row(
        sender: type[FormProgress], attempt: FormProgress, **kwargs: object
    ) -> None:
        seen.append(FormProgress.objects.get(pk=attempt.pk).asked)

    form_attempt_completed.connect(_read_stored_row)
    try:
        gated_sitting.progress.complete()
    finally:
        form_attempt_completed.disconnect(_read_stored_row)

    assert seen == [current_path(gated_sitting.progress).as_asked()]


# Free-text questions inside a ``strategy: QUIZ`` form.
#
# Authored content is not supposed to put a ``short_text``/``long_text`` question
# in a scored quiz — no demo course does. When it happens anyway, such a question
# has no options at all, so it can be neither matched against a correct set nor
# echoed back through ``selected_options``: it must not produce a review card.


def _quiz_with_free_text(
    question_type: str,
) -> tuple[Form, FormQuestion, QuestionOption, FormQuestion]:
    """A quiz with one answered-correctly choice question and one free-text question."""
    form: Form = FormFactory(strategy=FormStrategy.QUIZ)
    page = FormPageFactory(form=form, order=0)
    choice_question: FormQuestion = FormQuestionFactory(
        form_page=page, type="multiple_choice", order=0
    )
    correct_option: QuestionOption = QuestionOptionFactory(
        question=choice_question, correct=True
    )
    QuestionOptionFactory(question=choice_question, correct=False)
    free_text_question: FormQuestion = FormQuestionFactory(
        form_page=page, type=question_type, question="Explain your reasoning", order=1
    )
    return form, choice_question, correct_option, free_text_question


@pytest.mark.parametrize("question_type", ["short_text", "long_text"])
@pytest.mark.django_db
def test_free_text_question_produces_no_incorrect_answer_card(
    mock_site_context, question_type
):
    user = UserFactory()
    form, choice_question, correct_option, free_text_question = _quiz_with_free_text(
        question_type
    )
    form_progress = FormProgressFactory(user=user, form=form)
    choice_answer = QuestionAnswerFactory(
        form_progress=form_progress, question=choice_question
    )
    choice_answer.selected_options.add(correct_option)
    QuestionAnswerFactory(
        form_progress=form_progress,
        question=free_text_question,
        text_answer="Because the current has nowhere else to go.",
    )

    incorrect = form_progress.get_incorrect_quiz_answers()

    assert incorrect == []


@pytest.mark.django_db
def test_free_text_question_still_counts_toward_the_quiz_max_score(mock_site_context):
    """The score ceiling is deliberately left alone: an unscoreable question
    still raises max_score, so such a quiz cannot reach 100%."""
    user = UserFactory()
    form, choice_question, correct_option, _free_text = _quiz_with_free_text(
        "short_text"
    )
    form_progress = FormProgressFactory(user=user, form=form)
    answer = QuestionAnswerFactory(
        form_progress=form_progress, question=choice_question
    )
    answer.selected_options.add(correct_option)

    form_progress.score_quiz()

    form_progress.refresh_from_db()
    assert form_progress.scores == {"score": 1, "max_score": 2}


@pytest.mark.django_db
def test_complete_stamps_a_sitting_that_has_no_user(mock_site_context):
    progress = FormProgressFactory(user=None)

    progress.complete()

    assert progress.completed_time is not None


@pytest.mark.django_db
def test_a_file_on_a_user_less_sitting_is_stored_under_the_anonymous_prefix(
    mock_site_context,
):
    form_progress = FormProgressFactory(user=None)
    answer_file: QuestionAnswerFile = QuestionAnswerFileFactory(
        answer__form_progress=form_progress
    )

    assert str(answer_file.file.name).startswith(
        f"user_uploads/anonymous/{form_progress.pk}/form_answers/"
    )


@pytest.mark.django_db
def test_a_user_less_sitting_is_labelled_anonymous(mock_site_context):
    sitting = FormProgressFactory(user=None)

    assert str(sitting).startswith("Anonymous - ")


@pytest.mark.django_db
def test_deleting_an_option_that_gates_a_page_is_blocked(mock_site_context):
    option = QuestionOptionFactory()
    FormPageFactory(condition_option=option)

    with pytest.raises(RestrictedError), transaction.atomic():
        option.delete()


@pytest.mark.django_db
def test_deleting_a_form_removes_the_pages_gated_by_its_own_options(
    mock_site_context,
):
    option = QuestionOptionFactory()
    form = option.question.form_page.form
    gated = FormPageFactory(form=form, condition_option=option)

    form.delete()

    assert not FormPage.objects.filter(pk=gated.pk).exists()
    assert not QuestionOption.objects.filter(pk=option.pk).exists()


def _three_question_quiz(
    middle_type: str = "multiple_choice",
) -> tuple[FormProgress, list[FormQuestion]]:
    """An unanswered quiz sitting of three questions on one page, with no served paper."""
    form: Form = FormFactory(strategy=FormStrategy.QUIZ)
    page = FormPageFactory(form=form, order=0)
    questions: list[FormQuestion] = [
        FormQuestionFactory(form_page=page, type=question_type, order=order)
        for order, question_type in enumerate(
            ["multiple_choice", middle_type, "multiple_choice"]
        )
    ]
    for question in questions:
        if question.type == "multiple_choice":
            QuestionOptionFactory(question=question, correct=True, order=0)
    progress: FormProgress = FormProgressFactory(form=form)
    return progress, questions


def _serve_in_order(progress: FormProgress, served: list[FormQuestion]) -> None:
    progress.served_paper = served_paper_of(
        [(served[0].form_page, [*served])],
        {q: list(q.options.all()) for q in served if q.type == "multiple_choice"},
    )
    progress.save()


@pytest.mark.django_db
def test_incorrect_answers_carry_the_number_the_learner_was_shown(
    mock_site_context: object,
) -> None:
    progress, (first, second, third) = _three_question_quiz()
    _serve_in_order(progress, [third, first, second])

    incorrect = progress.get_incorrect_quiz_answers()

    assert [(item["question"], item["number"]) for item in incorrect] == [
        (third, 1),
        (first, 2),
        (second, 3),
    ]


@pytest.mark.django_db
def test_incorrect_answers_without_a_served_paper_carry_the_authored_number(
    mock_site_context: object,
) -> None:
    progress, (first, second, third) = _three_question_quiz()

    incorrect = progress.get_incorrect_quiz_answers()

    assert [(item["question"], item["number"]) for item in incorrect] == [
        (first, 1),
        (second, 2),
        (third, 3),
    ]


@pytest.mark.django_db
def test_incorrect_answers_numbers_skip_a_free_text_question(
    mock_site_context: object,
) -> None:
    progress, (first, free_text, third) = _three_question_quiz("short_text")
    _serve_in_order(progress, [third, free_text, first])

    incorrect = progress.get_incorrect_quiz_answers()

    assert [(item["question"], item["number"]) for item in incorrect] == [
        (third, 1),
        (first, 3),
    ]


@pytest.mark.django_db
def test_incorrect_answers_list_options_in_the_order_the_learner_was_shown(
    mock_site_context: object,
) -> None:
    form: Form = FormFactory(strategy=FormStrategy.QUIZ)
    page: FormPage = FormPageFactory(form=form, order=0)
    question: FormQuestion = FormQuestionFactory(
        form_page=page, type="checkboxes", order=0
    )
    options: list[QuestionOption] = [
        QuestionOptionFactory(question=question, order=order, correct=correct)
        for order, correct in enumerate([True, False, True, False])
    ]
    a, b, c, d = options
    progress: FormProgress = FormProgressFactory(form=form)
    progress.served_paper = served_paper_of(
        [(page, [question])], {question: [d, c, b, a]}
    )
    progress.save()
    answer = QuestionAnswerFactory(form_progress=progress, question=question)
    answer.selected_options.set([b, d])

    (item,) = progress.get_incorrect_quiz_answers()

    assert item["learner_selected"] == [d, b]
    assert item["correct_options"] == [c, a]


@pytest.mark.django_db
def test_incorrect_answers_without_a_served_paper_list_options_in_authored_order(
    mock_site_context: object,
) -> None:
    form: Form = FormFactory(strategy=FormStrategy.QUIZ)
    page: FormPage = FormPageFactory(form=form, order=0)
    question: FormQuestion = FormQuestionFactory(
        form_page=page, type="checkboxes", order=0
    )
    options: list[QuestionOption] = [
        QuestionOptionFactory(question=question, order=order, correct=correct)
        for order, correct in enumerate([True, False, True, False])
    ]
    a, b, c, d = options
    progress: FormProgress = FormProgressFactory(form=form)
    answer = QuestionAnswerFactory(form_progress=progress, question=question)
    answer.selected_options.set([d, b])

    (item,) = progress.get_incorrect_quiz_answers()

    assert item["learner_selected"] == [b, d]
    assert item["correct_options"] == [a, c]


@pytest.mark.django_db
def test_a_page_draw_of_zero_fails_validation(mock_site_context: object) -> None:
    page = FormPageFactory.build(draw=0)

    with pytest.raises(ValidationError) as excinfo:
        page.full_clean(exclude=["form", "site", "condition_option"])

    assert "draw" in excinfo.value.message_dict


def _even_drawing_page(draw: int | None = 1) -> FormPage:
    """A page of two groups, each a content block and two questions."""
    page: FormPage = FormPageFactory(
        form=FormFactory(strategy=FormStrategy.QUIZ), draw=draw
    )
    order = 0
    for group in ("a", "b"):
        FormContentFactory(form_page=page, order=order, group=group)
        FormQuestionFactory(form_page=page, order=order + 1, group=group)
        FormQuestionFactory(form_page=page, order=order + 2, group=group)
        order += 3
    return page


@pytest.mark.django_db
def test_adding_a_loose_question_to_a_drawing_page_fails_validation(
    mock_site_context: object,
) -> None:
    page = _even_drawing_page()
    loose = FormQuestionFactory.build(form_page=page, order=6)

    with pytest.raises(ValidationError, match="same number of questions"):
        loose.clean()


@pytest.mark.django_db
def test_moving_a_question_out_of_its_group_on_a_drawing_page_fails_validation(
    mock_site_context: object,
) -> None:
    page = _even_drawing_page()
    question = page.questions.get(order=2)
    question.order = 10

    with pytest.raises(ValidationError, match="same number of questions"):
        question.clean()


@pytest.mark.django_db
def test_a_content_block_with_no_question_on_a_drawing_page_fails_validation(
    mock_site_context: object,
) -> None:
    page = _even_drawing_page()
    stray = FormContentFactory.build(form_page=page, order=6)

    with pytest.raises(ValidationError, match="share a group with a question"):
        stray.clean()


@pytest.mark.django_db
def test_an_edit_that_keeps_a_drawing_page_even_passes_validation(
    mock_site_context: object,
) -> None:
    page = _even_drawing_page()
    question = page.questions.get(order=2)
    question.question = "Reworded"

    question.clean()


@pytest.mark.django_db
def test_uneven_units_are_allowed_on_a_page_with_no_draw(
    mock_site_context: object,
) -> None:
    page = _even_drawing_page(draw=None)
    loose = FormQuestionFactory.build(form_page=page, order=6)

    loose.clean()


def _quiz_with_questions(question_count: int, answered_rightly: int) -> FormProgress:
    """A served quiz sitting whose first `answered_rightly` questions are answered rightly."""
    form: Form = FormFactory(strategy=FormStrategy.QUIZ, quiz_pass_percentage=50)
    page: FormPage = FormPageFactory(form=form, order=0)
    progress: FormProgress = FormProgressFactory(form=form)
    questions: list[FormQuestion] = []
    for order in range(question_count):
        question: FormQuestion = FormQuestionFactory(
            form_page=page, type="multiple_choice", order=order
        )
        right: QuestionOption = QuestionOptionFactory(
            question=question, correct=True, order=0
        )
        QuestionOptionFactory(question=question, correct=False, order=1)
        questions.append(question)
        if order < answered_rightly:
            QuestionAnswerFactory(
                form_progress=progress, question=question
            ).selected_options.add(right)
    content: list[FormContent | FormQuestion] = [*questions]
    progress.served_paper = served_paper_of(
        [(page, content)],
        {question: list(question.options.order_by("order")) for question in questions},
    )
    progress.save()
    reloaded: FormProgress = FormProgress.objects.get(pk=progress.pk)
    return reloaded


@pytest.mark.django_db
def test_compute_quiz_scores_counts_the_rightly_answered_questions(
    mock_site_context: Site,
) -> None:
    progress = _quiz_with_questions(question_count=3, answered_rightly=2)

    scores = progress.compute_quiz_scores()

    assert scores == {"score": 2, "max_score": 3}


@pytest.mark.django_db
def test_compute_quiz_scores_reads_the_answers_it_is_given(
    mock_site_context: Site,
) -> None:
    progress = _quiz_with_questions(question_count=3, answered_rightly=2)
    answers = answers_by_question(progress)

    scores = progress.compute_quiz_scores(answers=answers)

    assert scores == {"score": 2, "max_score": 3}


@pytest.mark.django_db
def test_compute_quiz_scores_with_answers_stays_within_a_query_bound_as_questions_grow(
    mock_site_context: Site, django_assert_max_num_queries: DjangoAssertNumQueries
) -> None:
    progress = _quiz_with_questions(question_count=12, answered_rightly=12)
    answers = answers_by_question(progress)

    with django_assert_max_num_queries(6):
        scores = progress.compute_quiz_scores(answers=answers)

    assert scores == {"score": 12, "max_score": 12}


@pytest.mark.django_db
def test_the_size_of_a_stored_file_is_its_byte_count(
    answer_file: QuestionAnswerFile,
) -> None:
    assert answer_file.size_or_none == len(b"stored bytes")


@pytest.mark.django_db
def test_the_size_of_a_file_missing_from_storage_is_none(
    answer_file: QuestionAnswerFile,
) -> None:
    answer_file.file.storage.delete(answer_file.file.name)

    assert answer_file.size_or_none is None


@pytest.mark.django_db
def test_rendered_explanation_renders_markdown(mock_site_context) -> None:
    question = FormQuestionFactory(explanation="It is **bold** because.")

    assert "<strong>bold</strong>" in question.rendered_explanation()


@pytest.mark.django_db
def test_effective_declaration_text_is_the_authors_text_when_set(
    mock_site_context: object,
) -> None:
    form = FormFactory(declaration_text="Author wording.")

    assert form.effective_declaration_text() == "Author wording."


@pytest.mark.django_db
def test_effective_declaration_text_is_the_site_default_when_the_author_left_it_empty(
    mock_site_context: object,
) -> None:
    form = FormFactory(declaration_text="")

    with override_settings(FORM_DECLARATION_DEFAULT_TEXT="Project wording."):
        assert form.effective_declaration_text() == "Project wording."


@pytest.mark.django_db
def test_saving_a_stored_declaration_again_raises(mock_site_context: object) -> None:
    declaration = FormDeclarationFactory()
    declaration.typed_name = "Changed Name"

    with pytest.raises(ValueError, match="append-only"):
        declaration.save()


@pytest.mark.django_db
def test_queryset_update_of_declarations_raises(mock_site_context: object) -> None:
    FormDeclarationFactory()

    with pytest.raises(ValueError, match="append-only"):
        FormDeclaration.objects.update(typed_name="Changed Name")


@pytest.mark.django_db
def test_bulk_update_of_declarations_raises(mock_site_context: object) -> None:
    declaration = FormDeclarationFactory()
    declaration.typed_name = "Changed Name"

    with pytest.raises(ValueError, match="append-only"):
        FormDeclaration.objects.bulk_update([declaration], ["typed_name"])


@pytest.mark.django_db
def test_declarations_of_another_site_are_not_listed(mock_site_context: object) -> None:
    FormDeclarationFactory()
    with site_context(SiteFactory(domain="other.example.com", name="Other")):
        FormDeclarationFactory()

    assert FormDeclaration.objects.count() == 1


@pytest.mark.django_db
def test_deleting_the_form_progress_deletes_its_declaration(
    mock_site_context: object,
) -> None:
    declaration = FormDeclarationFactory()

    declaration.form_progress.delete()

    assert FormDeclaration.objects.count() == 0


@pytest.mark.django_db
def test_deleting_the_user_deletes_the_declaration(mock_site_context: object) -> None:
    declaration = FormDeclarationFactory()

    declaration.form_progress.user.delete()

    assert FormDeclaration.objects.count() == 0


@pytest.mark.parametrize(
    "factory", [FormFactory, FormPageFactory, FormContentFactory, FormQuestionFactory]
)
def test_not_retired_returns_the_live_form_rows_and_leaves_out_a_retired_one(
    mock_site_context, factory
):
    live = factory()
    retired = retire(factory())
    model = type(live)

    assert list(model.objects.not_retired()) == [live]
    assert set(model.objects.all()) == {live, retired}


@pytest.mark.django_db
def test_not_retired_leaves_out_a_retired_question_option(mock_site_context):
    question = FormQuestionFactory()
    live = QuestionOptionFactory(question=question)
    to_retire: QuestionOption = QuestionOptionFactory(question=question)
    retired = retire(to_retire)

    assert list(QuestionOption.objects.not_retired()) == [live]
    assert set(question.options.all()) == {live, retired}


@pytest.mark.django_db
def test_is_retired_on_a_question_option_follows_retired_at(mock_site_context):
    option: QuestionOption = QuestionOptionFactory()

    assert (option.is_retired, retire(option).is_retired) == (False, True)


@dataclass
class RetiredCorrectOption:
    form: Form
    page: FormPage
    question: FormQuestion
    kept_correct: QuestionOption
    retired_correct: QuestionOption
    progress: FormProgress


@pytest.fixture
def retired_correct_option(mock_site_context: object) -> RetiredCorrectOption:
    """A one-question quiz whose second correct option has retired; the learner
    ticked only the first."""
    form: Form = FormFactory(strategy=FormStrategy.QUIZ)
    page: FormPage = FormPageFactory(form=form, order=0)
    question: FormQuestion = FormQuestionFactory(
        form_page=page, type="checkboxes", order=0
    )
    kept_correct = QuestionOptionFactory(question=question, order=0, correct=True)
    retired_correct = retire(
        cast(
            "QuestionOption",
            QuestionOptionFactory(question=question, order=1, correct=True),
        )
    )
    progress: FormProgress = FormProgressFactory(form=form)
    QuestionAnswerFactory(
        form_progress=progress, question=question
    ).selected_options.add(kept_correct)
    return RetiredCorrectOption(
        form, page, question, kept_correct, retired_correct, progress
    )


@pytest.mark.django_db
def test_a_retired_correct_option_left_off_the_paper_does_not_make_the_answer_wrong(
    retired_correct_option: RetiredCorrectOption,
) -> None:
    sitting = retired_correct_option
    sitting.progress.served_paper = served_paper_of(
        [(sitting.page, [sitting.question])],
        {sitting.question: [sitting.kept_correct]},
    )
    sitting.progress.save()

    scores = sitting.progress.compute_quiz_scores()

    assert scores == {"score": 1, "max_score": 1}


@pytest.mark.django_db
def test_a_retired_correct_option_left_off_the_paper_is_not_listed_as_missed(
    retired_correct_option: RetiredCorrectOption,
) -> None:
    sitting = retired_correct_option
    sitting.progress.served_paper = served_paper_of(
        [(sitting.page, [sitting.question])],
        {sitting.question: [sitting.kept_correct]},
    )
    sitting.progress.save()

    assert sitting.progress.get_incorrect_quiz_answers() == []


@pytest.mark.django_db
def test_a_missed_question_lists_only_the_correct_options_the_paper_offered(
    retired_correct_option: RetiredCorrectOption,
) -> None:
    sitting = retired_correct_option
    sitting.progress.served_paper = served_paper_of(
        [(sitting.page, [sitting.question])],
        {sitting.question: [sitting.kept_correct]},
    )
    sitting.progress.save()
    sitting.progress.answers.get().selected_options.clear()

    (item,) = sitting.progress.get_incorrect_quiz_answers()

    assert item["correct_options"] == [sitting.kept_correct]


@pytest.mark.django_db
def test_a_sitting_with_no_paper_is_scored_on_every_option_retired_ones_included(
    retired_correct_option: RetiredCorrectOption,
) -> None:
    scores = retired_correct_option.progress.compute_quiz_scores()

    assert scores == {"score": 0, "max_score": 1}


@pytest.mark.django_db
def test_a_sitting_with_no_paper_is_still_marked_on_a_retired_question_and_page(
    retired_correct_option: RetiredCorrectOption,
) -> None:
    sitting = retired_correct_option
    retire(cast("FormQuestion", FormQuestionFactory(form_page=sitting.page, order=1)))
    retired_page = retire(cast("FormPage", FormPageFactory(form=sitting.form, order=1)))
    FormQuestionFactory(form_page=retired_page, order=0)

    scores = sitting.progress.compute_quiz_scores()

    assert scores["max_score"] == 3


@pytest.mark.django_db
def test_a_sitting_with_a_paper_is_still_marked_on_a_question_retired_after_it_started(
    two_question_quiz: TwoQuestionQuiz,
) -> None:
    page = two_question_quiz.first.form_page
    two_question_quiz.progress.served_paper = served_paper_of(
        [(page, [two_question_quiz.first, two_question_quiz.second])],
        {
            two_question_quiz.first: [two_question_quiz.first_right],
            two_question_quiz.second: [two_question_quiz.second_right],
        },
    )
    two_question_quiz.progress.save()
    retire(two_question_quiz.second)

    scores = two_question_quiz.progress.compute_quiz_scores()

    assert scores == {"score": 1, "max_score": 2}


@pytest.mark.django_db
def test_category_value_sum_sums_only_the_options_the_path_offers(
    mock_site_context: object,
) -> None:
    form: Form = FormFactory(strategy=FormStrategy.CATEGORY_VALUE_SUM)
    page = FormPageFactory(form=form, order=0, category="theme")
    question = FormQuestionFactory(
        form_page=page, type="multiple_choice", order=0, category="topic"
    )
    chosen = QuestionOptionFactory(question=question, order=0, value="2")
    retire(
        cast(
            "QuestionOption",
            QuestionOptionFactory(question=question, order=1, value="9"),
        )
    )
    progress: FormProgress = FormProgressFactory(form=form)
    QuestionAnswerFactory(
        form_progress=progress, question=question
    ).selected_options.add(chosen)

    progress.complete()

    progress.refresh_from_db()
    assert (progress.scores or {})["theme"]["max_score"] == 2


@pytest.mark.django_db
def test_question_number_skips_a_retired_question_and_a_retired_page(
    mock_site_context: object,
) -> None:
    form: Form = FormFactory()
    retired_page = retire(cast("FormPage", FormPageFactory(form=form, order=0)))
    FormQuestionFactory(form_page=retired_page, order=0)
    page = FormPageFactory(form=form, order=1)
    retire(cast("FormQuestion", FormQuestionFactory(form_page=page, order=0)))
    wanted = FormQuestionFactory(form_page=page, order=1)

    assert FormQuestion.objects.get(pk=wanted.pk).question_number() == 1
