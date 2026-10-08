from __future__ import annotations

import re

import pytest

from django.core.files.uploadedfile import SimpleUploadedFile
from django.template.loader import render_to_string
from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.form_engine.anonymous_sittings import ANONYMOUS_SITTINGS_SESSION_KEY
from freedom_ls.form_engine.factories import (
    FormContentFactory,
    FormFactory,
    FormPageFactory,
    FormProgressFactory,
    FormQuestionFactory,
    QuestionAnswerFileFactory,
)
from freedom_ls.form_engine.models import (
    FormPage,
    FormProgress,
    FormQuestion,
    FormStrategy,
    QuestionAnswerFile,
)
from freedom_ls.tests.images import png_bytes

# The three file endpoints an applicant reaches: attach, remove, download.
#
# Every one of them is scoped to the owner of the sitting. A file answer is a scan
# of someone's ID, so "the URL is unguessable" is not the control -- ownership is.


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

    cache_control = response["Cache-Control"]
    assert "no-store" in cache_control
    assert "private" in cache_control


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


# The two fragments a form page is built from, shared by the exam runner and
# the application shell: the page's own children, and why a submission was
# refused. They live here so the two shells cannot drift apart on either.


def _render_errors(required: str = "", rejected: str = "") -> str:
    return render_to_string(
        "form_engine/partials/answer_errors.html",
        {"required_answers_error": required, "rejected_answers_error": rejected},
    )


def _render_children(form_page: FormPage) -> str:
    return render_to_string(
        "form_engine/partials/page_children.html",
        {
            "form_page": form_page,
            "existing_answers": {},
            "rejected_answers": {},
            "read_only": False,
        },
    )


@pytest.mark.django_db
def test_no_errors_renders_nothing(mock_site_context):
    assert _render_errors().strip() == ""


@pytest.mark.django_db
def test_a_missing_required_answer_is_announced(mock_site_context):
    markup = _render_errors(required="Question 1 needs an answer.")

    assert 'data-testid="required-answers-error"' in markup
    assert 'role="alert"' in markup
    assert "Missing answers" in markup
    assert "Question 1 needs an answer." in markup


@pytest.mark.django_db
def test_an_invalid_answer_is_announced(mock_site_context):
    markup = _render_errors(rejected="Question 2 needs a valid answer.")

    assert 'data-testid="rejected-answers-error"' in markup
    assert "Invalid answers" in markup
    assert "Question 2 needs a valid answer." in markup


@pytest.mark.django_db
def test_one_error_does_not_draw_the_other(mock_site_context):
    markup = _render_errors(required="Question 1 needs an answer.")

    assert 'data-testid="rejected-answers-error"' not in markup


@pytest.mark.django_db
def test_both_errors_are_reported_together(mock_site_context):
    markup = _render_errors(required="Needs an answer.", rejected="Needs a valid one.")

    assert 'data-testid="required-answers-error"' in markup
    assert 'data-testid="rejected-answers-error"' in markup


@pytest.mark.django_db
def test_children_render_in_the_order_the_page_lays_them_out(mock_site_context):
    page: FormPage = FormPageFactory(order=0)
    FormContentFactory(form_page=page, content="Read this first.", order=0)
    question = FormQuestionFactory(
        form_page=page, type="short_text", order=1, question="Then answer this."
    )

    markup = _render_children(page)

    assert markup.index("Read this first.") < markup.index("Then answer this.")
    assert f'name="question_{question.id}"' in markup


@pytest.mark.django_db
def test_a_question_renders_as_a_fieldset(mock_site_context):
    page: FormPage = FormPageFactory(order=0)
    FormQuestionFactory(form_page=page, type="short_text", order=0)

    assert "<fieldset" in _render_children(page)


@pytest.mark.django_db
def test_a_page_with_no_children_renders_nothing(mock_site_context):
    page: FormPage = FormPageFactory(order=0)

    assert _render_children(page).strip() == ""


# ---------------------------------------------------------------------------
# A sitting no account owns yet is reached by the session that created it
# ---------------------------------------------------------------------------


@pytest.fixture
def held_sitting(
    mock_site_context, client
) -> tuple[FormProgress, FormQuestion, QuestionAnswerFile]:
    """An unowned sitting with a file attached, held by the test client's session."""
    form = FormFactory(strategy=FormStrategy.UNSCORED)
    page = FormPageFactory(form=form, order=0)
    question: FormQuestion = FormQuestionFactory(
        form_page=page, type="file_upload", order=0, required=True
    )
    form_progress: FormProgress = FormProgressFactory(form=form, user=None)
    answer_file: QuestionAnswerFile = QuestionAnswerFileFactory(
        answer__form_progress=form_progress, answer__question=question
    )
    session = client.session
    session[ANONYMOUS_SITTINGS_SESSION_KEY] = [str(form_progress.pk)]
    session.save()
    return form_progress, question, answer_file


@pytest.mark.django_db
def test_anonymous_owner_can_attach_a_file_on_a_session_held_sitting(
    mock_site_context, client
):
    form = FormFactory(strategy=FormStrategy.UNSCORED)
    question: FormQuestion = FormQuestionFactory(
        form_page=FormPageFactory(form=form, order=0), type="file_upload", order=0
    )
    form_progress: FormProgress = FormProgressFactory(form=form, user=None)
    session = client.session
    session[ANONYMOUS_SITTINGS_SESSION_KEY] = [str(form_progress.pk)]
    session.save()

    response = client.post(
        _upload_url(form_progress, question),
        {"file": _png_upload()},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    assert form_progress.answers.get(question=question).answer_file.pk


@pytest.mark.django_db
def test_anonymous_owner_can_remove_it(client, held_sitting):
    form_progress, question, _answer_file = held_sitting

    response = client.post(_remove_url(form_progress, question), HTTP_HX_REQUEST="true")

    assert response.status_code == 200
    assert not form_progress.answers.filter(question=question).exists()


@pytest.mark.django_db
def test_anonymous_owner_can_download_it(client, held_sitting):
    _form_progress, _question, answer_file = held_sitting

    response = client.get(_download_url(answer_file))

    assert response.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize("action", ["upload", "remove", "download"])
def test_anonymous_request_without_the_sitting_in_session_is_404(
    mock_site_context, client, held_sitting, action
):
    form_progress, question, answer_file = held_sitting
    session = client.session
    session[ANONYMOUS_SITTINGS_SESSION_KEY] = []
    session.save()
    if action == "upload":
        response = client.post(
            _upload_url(form_progress, question), {"file": _png_upload()}
        )
    elif action == "remove":
        response = client.post(_remove_url(form_progress, question))
    else:
        response = client.get(_download_url(answer_file))

    assert response.status_code == 404


@pytest.mark.django_db
def test_signed_in_user_cannot_touch_a_session_held_sitting_of_another_browser(
    mock_site_context, client, held_sitting
):
    form_progress, question, answer_file = held_sitting
    other = Client()
    other.force_login(UserFactory())

    upload = other.post(_upload_url(form_progress, question), {"file": _png_upload()})
    download = other.get(_download_url(answer_file))

    assert (upload.status_code, download.status_code) == (404, 404)


@pytest.mark.django_db
@pytest.mark.parametrize("action", ["upload", "remove", "download"])
def test_file_views_send_no_store_and_same_origin_referrer(
    client, held_sitting, action
):
    form_progress, question, answer_file = held_sitting
    if action == "upload":
        response = client.post(
            _upload_url(form_progress, question), {"file": _png_upload()}
        )
    elif action == "remove":
        response = client.post(_remove_url(form_progress, question))
    else:
        response = client.get(_download_url(answer_file))

    assert "no-store" in response["Cache-Control"]
    assert response["Referrer-Policy"] == "same-origin"
