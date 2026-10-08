"""The applicant's file endpoints: attach, remove, download.

Ownership or session possession is the whole control, never the
unguessability of a URL. A file answer is a scan of someone's identity document.
"""

from __future__ import annotations

from pathlib import Path

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from freedom_ls.accounts.decorators import never_cache_same_origin
from freedom_ls.accounts.throttling import is_ip_throttled
from freedom_ls.form_engine.anonymous_sittings import (
    held_sitting_ids,
    owned_or_held_q,
    sitting_for_request,
)
from freedom_ls.form_engine.config import config
from freedom_ls.form_engine.enums import QuestionType
from freedom_ls.form_engine.models import (
    FormProgress,
    FormQuestion,
    QuestionAnswer,
    QuestionAnswerFile,
)
from freedom_ls.form_engine.permissions import can_download_answer_files
from freedom_ls.form_engine.uploads import validate_and_sanitise

FILE_WIDGET_TEMPLATE = "form_engine/inputs/file_upload.html"


def _owned_file_question(
    request: HttpRequest, progress_pk: str, question_pk: str
) -> tuple[FormProgress, FormQuestion]:
    """The sitting and the file question, or 404.

    The question is matched against the sitting's own form, so a question id
    lifted from another form reaches nothing.
    """
    form_progress = sitting_for_request(request, progress_pk)
    question = get_object_or_404(
        FormQuestion,
        pk=question_pk,
        form_page__form=form_progress.form,
        type=QuestionType.FILE_UPLOAD,
    )
    return form_progress, question


def _render_file_widget(
    request: HttpRequest,
    form_progress: FormProgress,
    question: FormQuestion,
    answer_file: QuestionAnswerFile | None,
    *,
    error: str = "",
    notice: str = "",
    status: int = 200,
) -> HttpResponse:
    return render(
        request,
        FILE_WIDGET_TEMPLATE,
        {
            "question": question,
            "form_progress": form_progress,
            "answer_file": answer_file,
            "error": error,
            "notice": notice,
        },
        status=status,
    )


def _attached_file(
    form_progress: FormProgress, question: FormQuestion
) -> QuestionAnswerFile | None:
    """The file currently attached to this question, so an error draws over it."""
    return QuestionAnswerFile.objects.filter(
        answer__form_progress=form_progress, answer__question=question
    ).first()


@never_cache_same_origin
@require_POST
def partial_question_file_upload(
    request: HttpRequest, progress_pk: str, question_pk: str
) -> HttpResponse:
    """Attach a file to a file question, replacing whatever was there before."""
    form_progress, question = _owned_file_question(request, progress_pk, question_pk)
    if form_progress.completed_time is not None:
        return HttpResponse(status=409)

    if not request.user.is_authenticated and is_ip_throttled(
        request,
        namespace="form_engine.anonymous_upload",
        scope="upload",
        limit=config.FORM_ENGINE_ANONYMOUS_UPLOAD_LIMIT,
        window_seconds=config.FORM_ENGINE_ANONYMOUS_UPLOAD_WINDOW_SECONDS,
    ):
        return _render_file_widget(
            request,
            form_progress,
            question,
            _attached_file(form_progress, question),
            error="Too many uploads from your network. Try again in a few minutes.",
            status=422,
        )

    uploaded = request.FILES.get("file")
    # Read before validating, and truncated rather than rejected: the name is
    # only ever shown back to the applicant, and refusing an upload over a
    # display string would be absurd.
    original_filename = Path(uploaded.name or "").name[:255] if uploaded else ""
    try:
        content, extension = validate_and_sanitise(uploaded)
    except ValidationError as err:
        return _render_file_widget(
            request,
            form_progress,
            question,
            _attached_file(form_progress, question),
            error=err.messages[0],
            status=422,
        )

    with transaction.atomic():
        answer, _created = QuestionAnswer.objects.get_or_create(
            form_progress=form_progress, question=question, site=form_progress.site
        )
        try:
            answer_file = answer.answer_file
        except QuestionAnswerFile.DoesNotExist:
            answer_file = QuestionAnswerFile(answer=answer, site=form_progress.site)
        answer_file.original_filename = original_filename
        answer_file.file.save(f"file{extension}", content, save=True)

    return _render_file_widget(request, form_progress, question, answer_file)


@never_cache_same_origin
@require_POST
def partial_question_file_remove(
    request: HttpRequest, progress_pk: str, question_pk: str
) -> HttpResponse:
    """Detach the file from a file question, taking the stored object with it."""
    form_progress, question = _owned_file_question(request, progress_pk, question_pk)
    if form_progress.completed_time is not None:
        return HttpResponse(status=409)

    # Deleting the answer cascades to the file row, whose post_delete receiver
    # removes the stored object.
    form_progress.answers.filter(question=question).delete()

    notice = (
        "File removed. This question needs a file before you can submit."
        if question.required
        else "File removed."
    )
    return _render_file_widget(request, form_progress, question, None, notice=notice)


def stream_question_answer_file(answer_file: QuestionAnswerFile) -> FileResponse:
    """Stream a stored file as a private, never-cached attachment.

    The filename is rebuilt from a slugified `original_filename` plus the
    extension FLS chose, so nothing the applicant typed reaches the header.
    `as_attachment` with the site-wide SECURE_CONTENT_TYPE_NOSNIFF is what stops
    a file being rendered in the reader's origin.
    """
    extension = Path(answer_file.file.name or "").suffix
    # allow_unicode=True so a wholly non-Latin filename is not slugified away
    # to nothing for exactly the applicants whose name matters most.
    stem = slugify(Path(answer_file.original_filename).stem, allow_unicode=True)
    try:
        handle = answer_file.file.open("rb")
    # S3Storage raises this too: its _open loads the object eagerly and maps a
    # 404 to FileNotFoundError, so a key missing from the bucket lands here as well.
    except FileNotFoundError as exc:
        raise Http404 from exc
    response = FileResponse(
        handle, as_attachment=True, filename=f"{stem or 'file'}{extension}"
    )
    response["Cache-Control"] = "private, no-store, must-revalidate"
    return response


@never_cache_same_origin
def own_question_answer_file(request: HttpRequest, file_pk: str) -> FileResponse:
    """Serve an applicant back the file they attached."""
    allowed = owned_or_held_q(
        request,
        user_path="answer__form_progress__user",
        pk_path="answer__form_progress__pk",
        held_ids=held_sitting_ids(request),
    )
    answer_file = get_object_or_404(
        QuestionAnswerFile.objects.select_related("answer__form_progress").filter(
            allowed
        ),
        pk=file_pk,
    )
    return stream_question_answer_file(answer_file)


def question_answer_file_download_view(
    request: HttpRequest, object_id: str
) -> FileResponse:
    """The admin route that streams an applicant's attached file.

    The permission check is explicit because `admin_view` only guarantees
    staff, and not every staff user may read an applicant's papers.
    """
    if not can_download_answer_files(request.user):
        raise PermissionDenied
    answer_file = get_object_or_404(QuestionAnswerFile, pk=object_id)
    return stream_question_answer_file(answer_file)
