"""The learner import pages and the oversight thread paging view."""

from __future__ import annotations

from collections.abc import Iterator
from typing import NamedTuple, cast

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, QuerySet
from django.http import (
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseRedirect,
    StreamingHttpResponse,
)
from django.shortcuts import get_object_or_404, render
from django.template.defaultfilters import filesizeformat
from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlencode

from freedom_ls.accounts.models import User
from freedom_ls.base.csv_import import (
    MAX_UPLOAD_BYTES,
    CsvImportError,
    write_error_csv,
)
from freedom_ls.comms.config import config as comms_config
from freedom_ls.comms.messaging import decode_cursor
from freedom_ls.comms.messaging_views import (
    READ_ONLY_THREAD_ID,
    older_page_response,
)
from freedom_ls.comms.views import login_required_htmx_to
from freedom_ls.educator_interface.forms import LearnerImportForm
from freedom_ls.educator_interface.learner_import import (
    ERROR_CSV_HEADER,
    FULL_EXAMPLE_ROW,
    HEADER_DESCRIPTIONS,
    HEADERS,
    NOT_ADDED_LABELS,
    PREVIEW_LABEL_TONES,
    REQUIRED_HEADERS,
    TEMPLATE_EXAMPLE_ROWS,
    check_import_gate,
    create_learner_import,
    error_reason,
    error_rows,
    run_learner_import,
)
from freedom_ls.educator_interface.messaging import other_educator_conversations
from freedom_ls.educator_interface.panels.common.ids import uuid_or_404
from freedom_ls.educator_interface.panels.common.request import (
    OrganisationScopedRequest,
)
from freedom_ls.educator_interface.panels.learner.config import LearnerConfig
from freedom_ls.educator_interface.tasks import _run_learner_import_task
from freedom_ls.educator_interface.views import (
    _attach_organisation,
    scope_request,
    standalone_page_context,
)
from freedom_ls.learner_management.capabilities import can
from freedom_ls.learner_management.config import config as learner_management_config
from freedom_ls.learner_management.models import (
    Cohort,
    ImportLabel,
    ImportStatus,
    Learner,
    LearnerImport,
    LearnerImportRow,
)
from freedom_ls.learner_management.queries import VIEW_CONVERSATION, cohorts_visible_to
from freedom_ls.organisations.models import Organisation
from freedom_ls.panel_framework.config import config as panel_framework_config
from freedom_ls.panel_framework.models import RunStatus
from freedom_ls.panel_framework.panels import entry_count_text

__all__ = [
    "IMPORT_PREVIEW_PAGE_SIZE",
    "IMPORT_RESULT_ERROR_ROWS",
    "FormatRow",
    "_capped_error_rows",
    "_cohort_import_url",
    "_cohort_learners_url",
    "_count_of",
    "_csv_attachment",
    "_format_rows",
    "_import_cohort_or_404",
    "_import_denied",
    "_import_page",
    "_import_status_context",
    "_import_upload_url",
    "_import_url",
    "_label_counts",
    "_learners_url",
    "_requested_import_or_404",
    "_see_other",
    "learner_import",
    "learner_import_errors",
    "learner_import_preview",
    "learner_import_result",
    "learner_import_template",
    "partial_learner_import_status",
    "partial_oversight_thread_older",
]


@login_required_htmx_to("educator_interface:root")
def partial_oversight_thread_older(
    request: HttpRequest, organisation_slug: str, learner_pk: str, conversation_pk: str
) -> HttpResponse:
    """Older messages of a conversation under oversight. Authorised the way the
    learner page is, then by the oversight permission and the oversight set;
    records nothing, since the open that reached this page already did."""
    if not comms_config.MESSAGING_ENABLED:
        raise Http404
    _attach_organisation(request, organisation_slug)
    learner = cast(
        Learner, LearnerConfig.get_instance_view(request, learner_pk).instance
    )
    if not can(request.user, VIEW_CONVERSATION, learner):
        raise Http404
    conversation = get_object_or_404(
        other_educator_conversations(cast(User, request.user), learner),
        pk=uuid_or_404(conversation_pk),
    )
    cursor = decode_cursor(request.GET.get("before", ""))
    if cursor is None:
        return HttpResponseBadRequest("before must be a cursor")
    return older_page_response(
        request,
        conversation,
        cursor,
        older_url=request.path,
        thread_id=READ_ONLY_THREAD_ID,
    )


def _see_other(url: str) -> HttpResponseRedirect:
    """A 303, so the browser follows a POST with a GET of the next page."""
    return HttpResponseRedirect(url, status=303)


def _learners_url(organisation: Organisation) -> str:
    return reverse(
        "educator_interface:interface",
        kwargs={"organisation_slug": organisation.slug, "path_string": "learners"},
    )


def _import_url(name: str, organisation: Organisation, *args: str) -> str:
    return reverse(
        f"educator_interface:{name}",
        kwargs={
            "organisation_slug": organisation.slug,
            **({"import_id": args[0]} if args else {}),
        },
    )


class FormatRow(NamedTuple):
    name: str
    requirement: str
    description: str
    example: str


def _format_rows(cohort: Cohort | None) -> list[FormatRow]:
    """One row per accepted column, in header order. On a cohort import the
    cohort column is never read, so its row says so instead of describing it."""
    rows = []
    for index, name in enumerate(HEADERS):
        description = HEADER_DESCRIPTIONS[name]
        if cohort is not None and name == "cohort":
            description = f"Ignored: everyone goes into {cohort.name}."
        rows.append(
            FormatRow(
                name=name,
                requirement="Required" if name in REQUIRED_HEADERS else "Optional",
                description=description,
                example=FULL_EXAMPLE_ROW[index],
            )
        )
    return rows


def _import_page(
    request: HttpRequest,
    scoped: OrganisationScopedRequest,
    template: str,
    context: dict[str, object],
    status: int = 200,
) -> HttpResponse:
    page = standalone_page_context(
        scoped, heading="Import learners", section="learners"
    )
    page.update(context)
    return render(request, template, page, status=status)


def _import_denied(
    request: HttpRequest, scoped: OrganisationScopedRequest
) -> HttpResponse:
    """The 403 page for a user who can see the organisation but may not import."""
    return _import_page(
        request,
        scoped,
        "educator_interface/learner_import_denied.html",
        {
            **LearnerConfig.get_denied_context(scoped, None, None),
            "back_url": _learners_url(scoped.organisation),
        },
        status=403,
    )


IMPORT_PREVIEW_PAGE_SIZE = 50
IMPORT_RESULT_ERROR_ROWS = 50


def _label_counts(
    rows: QuerySet[LearnerImportRow], field: str
) -> list[dict[str, object]]:
    """The rows per label, in the order labels are declared, for the labels
    that occur."""
    counted = {
        item[field]: item["total"]
        for item in rows.exclude(**{f"{field}__isnull": True})
        .values(field)
        .annotate(total=Count("pk"))
    }
    return [
        {"label": label.value, "name": label.label, "count": counted[label.value]}
        for label in ImportLabel
        if label.value in counted
    ]


def _count_of(counts: list[dict[str, object]], *labels: str) -> int:
    return sum(cast(int, item["count"]) for item in counts if item["label"] in labels)


def _requested_import_or_404(
    request: HttpRequest, scoped: OrganisationScopedRequest, import_id: str
) -> LearnerImport:
    """The import only its requester may see. Anyone else, and an import of
    another organisation, gets the 404 a missing one does."""
    return cast(
        LearnerImport,
        get_object_or_404(
            LearnerImport.objects.select_related("organisation", "cohort").filter(
                organisation=scoped.organisation, requested_by=cast(User, request.user)
            ),
            pk=import_id,
        ),
    )


def _cohort_learners_url(cohort: Cohort) -> str:
    return reverse(
        "educator_interface:interface",
        kwargs={
            "organisation_slug": cohort.organisation.slug,
            "path_string": f"cohorts/{cohort.pk}/__tabs/learners",
        },
    )


def _cohort_import_url(
    name: str, organisation: Organisation, cohort: Cohort | None
) -> str:
    """An import page's URL, carrying `?cohort=` for a cohort import."""
    url = _import_url(name, organisation)
    if cohort is None:
        return url
    return f"{url}?{urlencode({'cohort': str(cohort.pk)})}"


def _import_upload_url(learner_import: LearnerImport) -> str:
    """The upload page that made this import: the cohort's, for a cohort import."""
    return _cohort_import_url(
        "learner_import", learner_import.organisation, learner_import.cohort
    )


def _import_cohort_or_404(
    request: HttpRequest, organisation: Organisation
) -> Cohort | None:
    """The cohort named by `?cohort=`, among the cohorts the user can see in
    the organisation; None when the parameter is absent. A value that is not a
    cohort id is a 404 like an unknown one."""
    cohort_id = request.GET.get("cohort")
    if not cohort_id:
        return None
    try:
        return get_object_or_404(
            cohorts_visible_to(cast(User, request.user), organisation).select_related(
                "organisation"
            ),
            pk=cohort_id,
        )
    except ValidationError as error:
        raise Http404("No such cohort.") from error


@login_required
def learner_import(request: HttpRequest, organisation_slug: str) -> HttpResponse:
    """The upload page of a learner import; a valid file becomes a previewed
    import and the reader is sent to its preview. With `?cohort=<id>` the
    learners are added to that cohort."""
    scoped = scope_request(request, organisation_slug)
    organisation = scoped.organisation
    user = cast(User, request.user)
    cohort = _import_cohort_or_404(request, organisation)
    if not check_import_gate(user, organisation, cohort):
        return _import_denied(request, scoped)
    form = LearnerImportForm(
        request.POST if request.method == "POST" else None,
        request.FILES if request.method == "POST" else None,
    )
    if request.method == "POST" and form.is_valid():
        try:
            created = create_learner_import(
                user, organisation, cohort, form.cleaned_data["file"]
            )
        except CsvImportError as error:
            form.add_error("file", str(error))
        else:
            return _see_other(
                _import_url("learner_import_preview", organisation, str(created.pk))
            )
    return _import_page(
        request,
        scoped,
        "educator_interface/learner_import_upload.html",
        {
            "form": form,
            "cohort": cohort,
            "format_rows": _format_rows(cohort),
            "max_rows": f"{learner_management_config.LEARNER_IMPORT_MAX_ROWS:,}",
            "max_file_size": filesizeformat(MAX_UPLOAD_BYTES),
            "template_url": _cohort_import_url(
                "learner_import_template", organisation, cohort
            ),
        },
        status=422 if form.errors else 200,
    )


@login_required
def learner_import_preview(
    request: HttpRequest, organisation_slug: str, import_id: str
) -> HttpResponse:
    """What confirming an import will do (GET), and the confirmation (POST)."""
    scoped = scope_request(request, organisation_slug)
    learner_import = _requested_import_or_404(request, scoped, import_id)
    user = cast(User, request.user)
    if not check_import_gate(user, learner_import.organisation, learner_import.cohort):
        return _import_denied(request, scoped)
    result_url = _import_url("learner_import_result", scoped.organisation, import_id)
    if learner_import.status != ImportStatus.PREVIEWED:
        return _see_other(result_url)
    rows = LearnerImportRow.objects.filter(learner_import=learner_import)
    counts = _label_counts(rows, "preview_label")
    add_count = learner_import.row_count - _count_of(counts, *NOT_ADDED_LABELS)
    in_background = add_count > panel_framework_config.BULK_BACKGROUND_THRESHOLD
    if request.method == "POST":
        # Only one of two simultaneous confirmations changes a row, so only one
        # of them runs or enqueues the import. Either way the runner claims
        # the queued import itself.
        started = LearnerImport.objects.filter(
            pk=learner_import.pk, status=ImportStatus.PREVIEWED
        ).update(status=ImportStatus.QUEUED)
        if started:
            site_id = scoped.organisation.site_id
            if in_background:
                _run_learner_import_task.enqueue(str(learner_import.pk), site_id)
            else:
                run_learner_import(str(learner_import.pk), site_id)
        return _see_other(result_url)
    # An unknown label shows every row rather than none.
    label = request.GET.get("label", "")
    if label not in ImportLabel.values:
        label = ""
    if label:
        shown = rows.filter(preview_label=label)
    else:
        # Error rows have their own block above the table, so the unfiltered
        # table holds only the rows that will be added or are already members.
        shown = rows.exclude(preview_label=ImportLabel.ERROR)
    page_obj = Paginator(
        shown.order_by("line_number"), IMPORT_PREVIEW_PAGE_SIZE
    ).get_page(request.GET.get("page"))
    for row in page_obj:
        row.tone = PREVIEW_LABEL_TONES[row.preview_label]
    template = "educator_interface/learner_import_preview.html"
    if request.headers.get("HX-Target") == "import-rows":
        # A page link swaps in only the rows card. Any other htmx request (a
        # redirect followed here, a navigation link) needs the whole page.
        template = f"{template}#rows"
    return _import_page(
        request,
        scoped,
        template,
        {
            "learner_import": learner_import,
            "page_obj": page_obj,
            "entry_count": entry_count_text(page_obj, "row", "rows"),
            "label": label,
            "pagination_params": urlencode({"label": label}) if label else "",
            "preview_url": _import_url(
                "learner_import_preview", scoped.organisation, import_id
            ),
            "upload_url": _import_upload_url(learner_import),
            "errors_url": _import_url(
                "learner_import_errors", scoped.organisation, import_id
            ),
            "label_counts": counts,
            "new_account_count": _count_of(counts, ImportLabel.NEW_ACCOUNT),
            "error_count": _count_of(counts, ImportLabel.ERROR),
            "error_rows": _capped_error_rows(learner_import),
            "add_count": add_count,
            "in_background": in_background,
        },
    )


def _csv_attachment(chunks: Iterator[str], filename: str) -> StreamingHttpResponse:
    response = StreamingHttpResponse(chunks, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
def learner_import_template(
    request: HttpRequest, organisation_slug: str
) -> HttpResponse | StreamingHttpResponse:
    """A CSV with the accepted headers and two example rows. Gated like the
    upload page that links to it, so `?cohort=` names the same cohort."""
    scoped = scope_request(request, organisation_slug)
    cohort = _import_cohort_or_404(request, scoped.organisation)
    if not check_import_gate(cast(User, request.user), scoped.organisation, cohort):
        return _import_denied(request, scoped)
    return _csv_attachment(
        write_error_csv(HEADERS, TEMPLATE_EXAMPLE_ROWS), "learner-import-template.csv"
    )


@login_required
def learner_import_errors(
    request: HttpRequest, organisation_slug: str, import_id: str
) -> HttpResponse | StreamingHttpResponse:
    """The rows of an import that were not added because of an error, with
    the reason for each, in the shape the import accepts plus a reason."""
    scoped = scope_request(request, organisation_slug)
    learner_import = _requested_import_or_404(request, scoped, import_id)
    if not check_import_gate(
        cast(User, request.user), learner_import.organisation, learner_import.cohort
    ):
        return _import_denied(request, scoped)
    # Built before the response is returned: the body is read after the
    # request's site scope has been cleared.
    rows = error_rows(learner_import).iterator(chunk_size=500)
    filename = f"learner-import-errors-{timezone.localdate().isoformat()}.csv"
    return _csv_attachment(
        write_error_csv(
            ERROR_CSV_HEADER,
            (
                (
                    row.email,
                    row.first_name,
                    row.last_name,
                    row.cohort_name,
                    error_reason(row),
                )
                for row in rows
            ),
        ),
        filename,
    )


def _capped_error_rows(learner_import: LearnerImport) -> list[dict[str, object]]:
    """The first IMPORT_RESULT_ERROR_ROWS error rows with their reasons."""
    return [
        {"row": row, "reason": error_reason(row)}
        for row in error_rows(learner_import)[:IMPORT_RESULT_ERROR_ROWS]
    ]


def _import_status_context(
    scoped: OrganisationScopedRequest, learner_import: LearnerImport
) -> dict[str, object]:
    """What `partials/run_status.html` renders for an import: the progress while
    it is queued or running, the outcome once it has finished or failed."""
    import_id = str(learner_import.pk)
    total = learner_import.row_count
    context: dict[str, object] = {
        "run": learner_import,
        "learner_import": learner_import,
        "noun": "rows",
        "total": total,
        "percentage": learner_import.processed_count * 100 // total if total else 100,
        "status_url": _import_url(
            "learner_import_status", scoped.organisation, import_id
        ),
        "result_template": "educator_interface/partials/learner_import_result_body.html",
        "result_on_failure": True,
        "in_progress": learner_import.status not in (RunStatus.DONE, RunStatus.FAILED),
    }
    if context["in_progress"]:
        return context
    counts = _label_counts(
        LearnerImportRow.objects.filter(learner_import=learner_import), "final_label"
    )
    added = total - _count_of(counts, *NOT_ADDED_LABELS)
    context.update(
        label_counts=counts,
        added_count=added,
        not_added_count=total - added,
        error_rows=_capped_error_rows(learner_import),
        error_count=_count_of(counts, ImportLabel.ERROR),
        errors_url=_import_url("learner_import_errors", scoped.organisation, import_id),
        new_account_count=_count_of(counts, ImportLabel.NEW_ACCOUNT),
        learners_url=(
            _cohort_learners_url(learner_import.cohort)
            if learner_import.cohort
            else _learners_url(scoped.organisation)
        ),
        upload_url=_import_upload_url(learner_import),
    )
    return context


@login_required
def learner_import_result(
    request: HttpRequest, organisation_slug: str, import_id: str
) -> HttpResponse:
    """What an import did, or how far it got."""
    scoped = scope_request(request, organisation_slug)
    learner_import = _requested_import_or_404(request, scoped, import_id)
    user = cast(User, request.user)
    if not check_import_gate(user, learner_import.organisation, learner_import.cohort):
        return _import_denied(request, scoped)
    if learner_import.status == ImportStatus.PREVIEWED:
        return _see_other(
            _import_url("learner_import_preview", scoped.organisation, import_id)
        )
    return _import_page(
        request,
        scoped,
        "educator_interface/learner_import_result.html",
        _import_status_context(scoped, learner_import),
    )


@login_required_htmx_to("educator_interface:root")
def partial_learner_import_status(
    request: HttpRequest, organisation_slug: str, import_id: str
) -> HttpResponse:
    """The polled fragment of `learner_import_result`."""
    scoped = scope_request(request, organisation_slug)
    learner_import = _requested_import_or_404(request, scoped, import_id)
    user = cast(User, request.user)
    if not check_import_gate(user, learner_import.organisation, learner_import.cohort):
        return _import_denied(request, scoped)
    if learner_import.status == ImportStatus.PREVIEWED:
        raise Http404("The import has not been confirmed.")
    context = _import_status_context(scoped, learner_import)
    response = render(request, "educator_interface/partials/run_status.html", context)
    if not context["in_progress"]:
        # The finished outcome has a heading and focus handling the polled
        # fragment cannot carry, so the whole page is rendered again.
        response["HX-Refresh"] = "true"
    return response
