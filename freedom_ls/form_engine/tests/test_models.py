from __future__ import annotations

from dataclasses import dataclass

import pytest

from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import ProtectedError, RestrictedError

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.form_engine.conditions import current_path
from freedom_ls.form_engine.factories import (
    FormContentFactory,
    FormFactory,
    FormPageFactory,
    FormProgressFactory,
    FormQuestionFactory,
    QuestionAnswerFactory,
    QuestionAnswerFileFactory,
    QuestionOptionFactory,
)
from freedom_ls.form_engine.models import (
    Form,
    FormPage,
    FormProgress,
    FormQuestion,
    FormStrategy,
    QuestionAnswerFile,
    QuestionOption,
    question_answer_file_upload_to,
)
from freedom_ls.form_engine.signals import form_attempt_completed

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
    form_progress: FormProgress = FormProgressFactory()
    form_progress.record_page_reached(3)

    form_progress.record_page_reached(1)

    form_progress.refresh_from_db()
    assert form_progress.furthest_page_reached == 3


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


# Completing a sitting that branches: the answers it was not asked are dropped
# and the path it was asked is recorded.


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
