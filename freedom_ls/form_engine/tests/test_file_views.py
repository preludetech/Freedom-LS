"""The three file endpoints an applicant reaches: attach, remove, download.

Every one of them is scoped to the owner of the sitting. A file answer is a scan
of someone's ID, so "the URL is unguessable" is not the control -- ownership is.
"""

from __future__ import annotations

import re

import pytest

from django.core.files.uploadedfile import SimpleUploadedFile
from django.template.loader import render_to_string
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormProgressFactory,
    FormQuestionFactory,
    QuestionAnswerFileFactory,
)
from freedom_ls.form_engine.models import (
    FormProgress,
    FormQuestion,
    FormStrategy,
    QuestionAnswerFile,
)
from freedom_ls.tests.images import png_bytes


@pytest.fixture
def sitting(mock_site_context) -> tuple[FormProgress, FormQuestion]:
    """An open sitting with one required file question on its only page."""
    form = FormFactory(strategy=FormStrategy.UNSCORED)
    page = FormPageFactory(form=form, order=0)
    question: FormQuestion = FormQuestionFactory(
        form_page=page, type="file_upload", order=0, required=True
    )
    form_progress: FormProgress = FormProgressFactory(form=form, user=UserFactory())
    return form_progress, question


def _upload_url(form_progress: FormProgress, question: FormQuestion) -> str:
    return reverse(
        "form_engine:question_file_upload",
        kwargs={"progress_pk": form_progress.pk, "question_pk": question.pk},
    )


def _remove_url(form_progress: FormProgress, question: FormQuestion) -> str:
    return reverse(
        "form_engine:question_file_remove",
        kwargs={"progress_pk": form_progress.pk, "question_pk": question.pk},
    )


def _png_upload() -> SimpleUploadedFile:
    return SimpleUploadedFile("id-scan.png", png_bytes())


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_the_owner_can_attach_a_file(mock_site_context, client, sitting):
    form_progress, question = sitting
    client.force_login(form_progress.user)

    response = client.post(
        _upload_url(form_progress, question),
        {"file": _png_upload()},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200


@pytest.mark.django_db
def test_attaching_a_file_stores_it_against_the_answer(
    mock_site_context, client, sitting
):
    form_progress, question = sitting
    client.force_login(form_progress.user)

    client.post(
        _upload_url(form_progress, question),
        {"file": _png_upload()},
        HTTP_HX_REQUEST="true",
    )

    answer = form_progress.answers.get(question=question)
    assert answer.answer_file.original_filename == "id-scan.png"


@pytest.mark.django_db
def test_an_executable_named_png_is_refused_with_422(
    mock_site_context, client, sitting
):
    form_progress, question = sitting
    client.force_login(form_progress.user)

    response = client.post(
        _upload_url(form_progress, question),
        {"file": SimpleUploadedFile("payload.png", b"\x7fELF" + b"\x00" * 64)},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 422


@pytest.mark.django_db
def test_a_refused_upload_stores_nothing(mock_site_context, client, sitting):
    form_progress, question = sitting
    client.force_login(form_progress.user)

    client.post(
        _upload_url(form_progress, question),
        {"file": SimpleUploadedFile("payload.png", b"\x7fELF" + b"\x00" * 64)},
        HTTP_HX_REQUEST="true",
    )

    assert form_progress.answers.count() == 0


@pytest.mark.django_db
def test_another_user_cannot_attach_to_someone_elses_sitting(
    mock_site_context, client, sitting
):
    form_progress, question = sitting
    client.force_login(UserFactory())

    response = client.post(
        _upload_url(form_progress, question),
        {"file": _png_upload()},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_submitted_application_refuses_a_new_file(mock_site_context, client, sitting):
    form_progress, question = sitting
    form_progress.complete()
    client.force_login(form_progress.user)

    response = client.post(
        _upload_url(form_progress, question),
        {"file": _png_upload()},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 409


@pytest.mark.django_db
def test_a_question_from_another_form_is_not_found(mock_site_context, client, sitting):
    form_progress, _question = sitting
    other_page = FormPageFactory(order=0)
    stranger: FormQuestion = FormQuestionFactory(
        form_page=other_page, type="file_upload", order=0
    )
    client.force_login(form_progress.user)

    response = client.post(
        _upload_url(form_progress, stranger),
        {"file": _png_upload()},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_non_file_question_is_not_found(mock_site_context, client, sitting):
    form_progress, question = sitting
    text_question: FormQuestion = FormQuestionFactory(
        form_page=question.form_page, type="short_text", order=1
    )
    client.force_login(form_progress.user)

    response = client.post(
        _upload_url(form_progress, text_question),
        {"file": _png_upload()},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Remove
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_removing_a_file_clears_the_answer_row(mock_site_context, client, sitting):
    form_progress, question = sitting
    client.force_login(form_progress.user)
    client.post(
        _upload_url(form_progress, question),
        {"file": _png_upload()},
        HTTP_HX_REQUEST="true",
    )

    client.post(_remove_url(form_progress, question), HTTP_HX_REQUEST="true")

    assert form_progress.answers.filter(question=question).count() == 0


@pytest.mark.django_db
def test_removing_a_file_deletes_the_stored_object(mock_site_context, client, sitting):
    form_progress, question = sitting
    client.force_login(form_progress.user)
    client.post(
        _upload_url(form_progress, question),
        {"file": _png_upload()},
        HTTP_HX_REQUEST="true",
    )
    stored = QuestionAnswerFile.objects.get(answer__question=question)
    storage, name = stored.file.storage, stored.file.name

    client.post(_remove_url(form_progress, question), HTTP_HX_REQUEST="true")

    assert storage.exists(name) is False


@pytest.mark.django_db
def test_removing_a_required_file_says_one_is_still_needed(
    mock_site_context, client, sitting
):
    form_progress, question = sitting
    client.force_login(form_progress.user)
    client.post(
        _upload_url(form_progress, question),
        {"file": _png_upload()},
        HTTP_HX_REQUEST="true",
    )

    response = client.post(_remove_url(form_progress, question), HTTP_HX_REQUEST="true")

    assert "needs a file before you can submit" in response.content.decode()


@pytest.mark.django_db
def test_another_user_cannot_remove_someone_elses_file(
    mock_site_context, client, sitting
):
    form_progress, question = sitting
    client.force_login(UserFactory())

    response = client.post(_remove_url(form_progress, question), HTTP_HX_REQUEST="true")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------


def _download_url(answer_file: QuestionAnswerFile) -> str:
    return reverse(
        "form_engine:own_question_answer_file", kwargs={"file_pk": answer_file.pk}
    )


@pytest.mark.django_db
def test_the_owner_can_download_their_own_pending_file(mock_site_context, client):
    answer_file: QuestionAnswerFile = QuestionAnswerFileFactory()
    client.force_login(answer_file.answer.form_progress.user)

    response = client.get(_download_url(answer_file))

    assert response.status_code == 200


@pytest.mark.django_db
def test_the_download_is_served_as_an_attachment(mock_site_context, client):
    answer_file: QuestionAnswerFile = QuestionAnswerFileFactory(
        original_filename="My Passport Page.png"
    )
    client.force_login(answer_file.answer.form_progress.user)

    response = client.get(_download_url(answer_file))

    assert (
        response["Content-Disposition"] == 'attachment; filename="my-passport-page.jpg"'
    )


@pytest.mark.django_db
def test_the_download_is_never_cached(mock_site_context, client):
    answer_file: QuestionAnswerFile = QuestionAnswerFileFactory()
    client.force_login(answer_file.answer.form_progress.user)

    response = client.get(_download_url(answer_file))

    assert response["Cache-Control"] == "private, no-store, must-revalidate"


@pytest.mark.django_db
def test_another_user_cannot_download_someone_elses_file(mock_site_context, client):
    answer_file: QuestionAnswerFile = QuestionAnswerFileFactory()
    client.force_login(UserFactory())

    response = client.get(_download_url(answer_file))

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_file_missing_from_storage_is_not_found(mock_site_context, client):
    answer_file: QuestionAnswerFile = QuestionAnswerFileFactory()
    answer_file.file.storage.delete(answer_file.file.name)
    client.force_login(answer_file.answer.form_progress.user)

    response = client.get(_download_url(answer_file))

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# The widget the two fragment views return
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_the_attached_widget_names_the_file_the_applicant_chose(
    mock_site_context, client, sitting
):
    form_progress, question = sitting
    client.force_login(form_progress.user)

    response = client.post(
        _upload_url(form_progress, question),
        {"file": _png_upload()},
        HTTP_HX_REQUEST="true",
    )

    assert "id-scan.png" in response.content.decode()


@pytest.mark.django_db
def test_the_attached_widget_links_to_the_download(mock_site_context, client, sitting):
    form_progress, question = sitting
    client.force_login(form_progress.user)

    response = client.post(
        _upload_url(form_progress, question),
        {"file": _png_upload()},
        HTTP_HX_REQUEST="true",
    )

    stored = QuestionAnswerFile.objects.get(answer__question=question)
    assert _download_url(stored) in response.content.decode()


@pytest.mark.django_db
def test_the_attached_widgets_download_link_is_a_tap_sized_button(
    mock_site_context, client, sitting
):
    """The Download control sits beside the Replace/Remove buttons, both of
    which are padded btn-sm buttons. An underlined text link there falls
    below the 24px minimum tap target, so Download has to be styled as a
    button too, matching the fix already applied on the check-your-answers
    page.
    """
    form_progress, question = sitting
    client.force_login(form_progress.user)

    response = client.post(
        _upload_url(form_progress, question),
        {"file": _png_upload()},
        HTTP_HX_REQUEST="true",
    )

    stored = QuestionAnswerFile.objects.get(answer__question=question)
    download_url = _download_url(stored)
    content = response.content.decode()
    anchor_match = re.search(rf'<a[^>]*href="{re.escape(download_url)}"[^>]*>', content)

    assert anchor_match is not None
    anchor_tag = anchor_match.group(0)
    assert "btn" in anchor_tag
    assert "btn-sm" in anchor_tag


@pytest.mark.django_db
def test_the_empty_widget_offers_a_picker_for_the_allowed_extensions(
    mock_site_context, client, sitting
):
    form_progress, question = sitting
    client.force_login(form_progress.user)

    response = client.post(_remove_url(form_progress, question), HTTP_HX_REQUEST="true")

    assert 'accept=".jpeg,.jpg,.pdf,.png"' in response.content.decode()


@pytest.mark.django_db
def test_the_widget_announces_its_own_changes(mock_site_context, client, sitting):
    """Attaching and removing both happen without a page load, so the outcome
    has to be announced where it happened.
    """
    form_progress, question = sitting
    client.force_login(form_progress.user)

    response = client.post(_remove_url(form_progress, question), HTTP_HX_REQUEST="true")

    assert 'aria-live="polite"' in response.content.decode()


@pytest.mark.django_db
def test_a_refused_upload_renders_its_reason_in_the_widget(
    mock_site_context, client, sitting
):
    form_progress, question = sitting
    client.force_login(form_progress.user)

    response = client.post(
        _upload_url(form_progress, question),
        {"file": SimpleUploadedFile("notes.docx", png_bytes())},
        HTTP_HX_REQUEST="true",
    )

    assert "Upload a JPEG, PNG or PDF." in response.content.decode()


# ---------------------------------------------------------------------------
# The picker's face
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_the_empty_picker_is_a_button_wrapping_the_input(mock_site_context, sitting):
    """A bare file input gives no hint of where to click. The label carries
    the button styling, and the real input rides inside it."""
    form_progress, question = sitting

    markup = render_to_string(
        "form_engine/inputs/file_upload.html",
        {"question": question, "form_progress": form_progress, "answer_file": None},
    )

    label_start = markup.index("<label")
    label_end = markup.index("</label>")
    label = markup[label_start:label_end]
    assert "btn btn-secondary" in label
    assert "cursor-pointer" in label
    assert "Choose a file" in label
    assert 'type="file"' in label


@pytest.mark.django_db
def test_the_replace_picker_sits_level_with_the_remove_button(
    mock_site_context, client, sitting
):
    """The base layer gives every label a bottom margin, which is what used to
    push Replace a few pixels above Remove."""
    form_progress, question = sitting
    client.force_login(form_progress.user)

    response = client.post(
        _upload_url(form_progress, question),
        {"file": _png_upload()},
        HTTP_HX_REQUEST="true",
    )

    markup = response.content.decode()
    label = markup[markup.index("<label") : markup.index("</label>")]
    assert "Replace" in label
    assert "mb-0" in label
