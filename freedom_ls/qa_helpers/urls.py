# QA-TEMP: URL routing for toast QA playground. DEBUG-only.

from django.urls import path

from . import toast_views

app_name = "qa_helpers"

urlpatterns = [
    path("toasts/full/", toast_views.full_page_toasts, name="toasts_full"),
    path("toasts/htmx-success/", toast_views.htmx_success, name="toasts_htmx_success"),
    path("toasts/htmx-error/", toast_views.htmx_error, name="toasts_htmx_error"),
    path("toasts/playground/", toast_views.playground, name="toasts_playground"),
]
