# QA-TEMP: Toast playground views.
#
# These endpoints exist to support manual QA of the toast notification
# system (HTMX OOB delivery + full-page render path). They are wired up
# only when DEBUG=True via qa_helpers/urls.py. Remove once the toast
# spec QA is complete.
#
# `htmx_success` and `htmx_error` deliberately render `partials/messages.html`
# in OOB mode in the view itself — the pattern that originally exposed the
# double-OOB bug documented in qa_report.md (Bug 1). The production
# `HtmxMessagesMiddleware` must tolerate this pattern and emit exactly one
# OOB fragment, so these endpoints double as a regression check.

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

_SEVERITY_TO_LEVEL = {
    "success": messages.SUCCESS,
    "info": messages.INFO,
    "warning": messages.WARNING,
    "error": messages.ERROR,
    "debug": messages.DEBUG,
}


@require_GET
def full_page_toasts(request: HttpRequest) -> HttpResponse:
    """Queue N django messages then redirect to / so they render on next page."""
    severity = request.GET.get("severity", "info").lower()
    try:
        count = int(request.GET.get("count", "1"))
    except ValueError:
        count = 1
    text = request.GET.get("text", f"QA full-page {severity} toast")

    level = _SEVERITY_TO_LEVEL.get(severity, messages.INFO)
    for i in range(max(1, count)):
        label = f"{text} ({i + 1}/{count})" if count > 1 else text
        messages.add_message(request, level, label)

    return redirect("/")


@require_POST
def htmx_success(request: HttpRequest) -> HttpResponse:
    messages.success(request, "HTMX success toast")
    return render(
        request,
        "partials/messages.html",
        {"messages": messages.get_messages(request), "oob": True},
    )


@require_POST
def htmx_error(request: HttpRequest) -> HttpResponse:
    messages.error(request, "HTMX error toast")
    response = render(
        request,
        "partials/messages.html",
        {"messages": messages.get_messages(request), "oob": True},
    )
    response.status_code = 422
    return response


@require_GET
def playground(request: HttpRequest) -> HttpResponse:
    return render(request, "qa_helpers/toast_playground.html")
