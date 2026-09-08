from django.urls import path

from . import views

app_name = "course_applications"

urlpatterns = [
    path("apply/<slug:course_slug>/", views.apply, name="apply"),
    path("status/<uuid:pk>/", views.application_status, name="status"),
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
]
