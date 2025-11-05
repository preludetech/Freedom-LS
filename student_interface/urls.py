from django.urls import path
from . import views

app_name = "student_interface"


# TODO: Use slugs instead of uuids for topics, collections and forms
# slugs should be generated against the titles of the different things


urlpatterns = [
    path("topics/<uuid:pk>/", views.topic_detail, name="topic_detail"),
    path(
        "collections/<uuid:collection_pk>/topics/<uuid:pk>/",
        views.topic_detail,
        name="topic_detail_in_collection",
    ),
    path("collections/<uuid:pk>/", views.course_home, name="course_home"),
    path("forms/<uuid:pk>/", views.form_detail, name="form_detail"),
    path(
        "collections/<uuid:collection_pk>/forms/<uuid:pk>/",
        views.form_detail,
        name="form_detail_in_collection",
    ),
    path("forms/<uuid:pk>/start/", views.form_start, name="form_start"),
    path(
        "form_progress/<uuid:pk>/<int:page_number>/",
        views.form_fill_page,
        name="form_fill_page",
    ),
]
