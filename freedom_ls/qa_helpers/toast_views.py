# QA-TEMP: Toast playground views.
#
# These endpoints exist to support manual QA of the toast notification
# system (HTMX OOB delivery + full-page render path). They are wired up
# only when DEBUG=True via qa_helpers/urls.py. Remove once the toast
# spec QA is complete.

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
    """Return 200 — `HtmxMessagesMiddleware` appends the OOB toast fragment."""
    messages.success(request, "HTMX success toast")
    return HttpResponse(b"", status=200, content_type="text/html")


@require_POST
def htmx_error(request: HttpRequest) -> HttpResponse:
    """Return 422 — `HtmxMessagesMiddleware` appends the OOB toast fragment."""
    messages.error(request, "HTMX error toast")
    return HttpResponse(b"", status=422, content_type="text/html")


@require_GET
def playground(request: HttpRequest) -> HttpResponse:
    return render(request, "qa_helpers/toast_playground.html")
