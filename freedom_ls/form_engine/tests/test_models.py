from __future__ import annotations

import pytest

from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import ProtectedError

from freedom_ls.accounts.factories import UserFactory
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
def test_upload_key_is_keyed_by_sitting(mock_site_context, answer_file):
    sitting_id = answer_file.answer.form_progress_id

    assert answer_file.file.name.startswith(f"user_uploads/form_answers/{sitting_id}/")


@pytest.mark.django_db
def test_the_key_takes_its_extension_from_the_name_fls_chose(
    mock_site_context, answer_file
):
    """The applicant's own filename never reaches a storage key."""
    key = question_answer_file_upload_to(answer_file, "file.pdf")

    assert key.endswith(f"{answer_file.pk}.pdf")


@pytest.mark.django_db
def test_removing_the_answer_deletes_the_stored_object(mock_site_context, answer_file):
    storage, name = answer_file.file.storage, answer_file.file.name
    answer = answer_file.answer

    answer.delete()

    assert storage.exists(name) is False


@pytest.mark.django_db
def test_removing_the_answer_deletes_the_answer_row(mock_site_context, answer_file):
    answer = answer_file.answer

    answer.delete()

    assert QuestionAnswerFile.objects.filter(pk=answer_file.pk).exists() is False


@pytest.mark.django_db
def test_deleting_the_applicant_deletes_the_stored_object(
    mock_site_context, answer_file
):
    storage, name = answer_file.file.storage, answer_file.file.name

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


@pytest.mark.django_db
def test_get_current_page_number_no_answers(mock_site_context):
    """An attempt with nothing answered resumes on the first page."""
    form = FormFactory()
    _page_with_question(form, order=0)
    _page_with_question(form, order=1)

    form_progress: FormProgress = FormProgressFactory(user=UserFactory(), form=form)

    assert form_progress.get_current_page_number() == 1


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

    assert form_progress.get_current_page_number() == 2


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

    assert form_progress.get_current_page_number() == 2


@pytest.mark.django_db
def test_get_current_page_number_page_with_text_only(mock_site_context):
    """A page carrying only content has nothing to answer, so it is not resumed on."""
    form = FormFactory()
    text_only_page = FormPageFactory(form=form, title="Page 1", order=0)
    FormContentFactory(form_page=text_only_page, content="Intro text", order=0)
    _page_with_question(form, order=1)

    form_progress: FormProgress = FormProgressFactory(user=UserFactory(), form=form)

    assert form_progress.get_current_page_number() == 2


@pytest.mark.django_db
def test_record_page_reached_remembers_the_furthest_page(mock_site_context):
    form_progress: FormProgress = FormProgressFactory()
    form_progress.record_page_reached(3)

    form_progress.record_page_reached(1)

    form_progress.refresh_from_db()
    assert form_progress.furthest_page_reached == 3


@pytest.mark.django_db
def test_str_names_an_unclaimed_sitting(mock_site_context):
    form_progress = FormProgressFactory(user=None)

    assert str(form_progress) == (
        f"unclaimed sitting {form_progress.pk} - {form_progress.form.title}"
    )


@pytest.mark.django_db
def test_answer_str_names_an_unclaimed_sitting(mock_site_context):
    answer = QuestionAnswerFactory(form_progress=FormProgressFactory(user=None))

    assert str(answer).startswith(f"unclaimed sitting {answer.form_progress_id} - ")


@pytest.mark.django_db
def test_complete_with_null_user_sends_the_signal(mock_site_context):
    from freedom_ls.form_engine.signals import form_attempt_completed

    received: list[object] = []

    def _capture(sender: object, user: object, **kwargs: object) -> None:
        received.append(user)

    form_attempt_completed.connect(_capture)
    try:
        FormProgressFactory(user=None).complete()
    finally:
        form_attempt_completed.disconnect(_capture)

    assert received == [None]


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
