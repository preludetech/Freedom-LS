"""A stored answer file is PII. Its key is namespaced by the applicant so an
erasure request has a prefix to sweep, and nothing may abandon an object in the
bucket: removing an answer, deleting the applicant, or replacing the file all
have to take the old object with them.
"""

from __future__ import annotations

import pytest

from django.core.files.base import ContentFile

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.form_engine.factories import (
    FormPageFactory,
    FormProgressFactory,
    QuestionAnswerFactory,
    QuestionAnswerFileFactory,
)
from freedom_ls.form_engine.models import (
    QuestionAnswerFile,
    question_answer_file_upload_to,
)


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
