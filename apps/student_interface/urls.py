from django.urls import path
from . import views

app_name = "student_interface"

urlpatterns = [
    path("topics/<slug:topic_slug>/", views.topic_detail, name="topic_detail"),
    path(
        "collections/<slug:collection_slug>/topics/<slug:topic_slug>/",
        views.topic_detail,
        name="topic_detail_in_collection",
    ),
    path(
        "collections/<slug:collection_slug>/", views.course_home, name="course_home"
    ),
    path("forms/<slug:form_slug>/", views.form_detail, name="form_detail"),
    path(
        "collections/<slug:collection_slug>/forms/<slug:form_slug>/",
        views.form_detail,
        name="form_detail_in_collection",
    ),
    path("forms/<slug:form_slug>/start/", views.form_start, name="form_start"),
    path(
        "form_progress/<uuid:pk>/<int:page_number>/",
        views.form_fill_page,
        name="form_fill_page",
    ),
    path(
        "form_progress/<uuid:pk>/complete/",
        views.form_complete,
        name="form_complete",
    ),
]
