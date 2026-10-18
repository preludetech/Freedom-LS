from django.urls import path

from . import views

app_name = "course_applications"

urlpatterns = [
    path("apply/<slug:course_slug>/", views.apply, name="apply"),
    path(
        "apply/<slug:course_slug>/your-details/",
        views.applicant_details,
        name="applicant_details",
    ),
    path("status/<uuid:pk>/", views.application_status, name="status"),
    path(
        "status/<uuid:pk>/change-email/",
        views.change_applicant_email,
        name="change_applicant_email",
    ),
    path(
        "application/<uuid:pk>/page/<int:page_number>/",
        views.application_form_page,
        name="form_page",
    ),
    path(
        "application/<uuid:pk>/check-your-answers/",
        views.application_check_answers,
        name="check_answers",
    ),
    path("claim/<str:token>/", views.claim_application, name="claim"),
]
