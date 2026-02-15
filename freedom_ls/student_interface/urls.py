from django.urls import path
from . import views

app_name = "student_interface"

urlpatterns = [
    path("", views.home, name="home"),
    path("all-courses/", views.all_courses, name="all_courses"),
    path("partials/courses/", views.partial_list_courses, name="partial_list_courses"),
    path(
        "partials/courses/<slug:course_slug>/toc",
        views.partial_course_toc,
        name="partial_course_toc",
    ),
    path("courses/<slug:course_slug>/", views.course_home, name="course_home"),
    path(
        "courses/<slug:course_slug>/register/",
        views.register_for_course,
        name="register_for_course",
    ),
    path(
        "courses/<slug:course_slug>/<int:index>/",
        views.view_course_item,
        name="view_course_item",
    ),
    path(
        "courses/<slug:course_slug>/<int:index>/start_form",
        views.form_start,
        name="form_start",
    ),
    path(
        "courses/<slug:course_slug>/<int:index>/fill_form/<int:page_number>",
        views.form_fill_page,
        name="form_fill_page",
    ),
    path(
        "courses/<slug:course_slug>/<int:index>/complete",
        views.course_form_complete,
        name="course_form_complete",
    ),
    path(
        "courses/<slug:course_slug>/finish/",
        views.course_finish,
        name="course_finish",
    ),
    ### Check these
    # path("topics/<slug:topic_slug>/", views.topic_detail, name="topic_detail"),
    # path(
    #     "collections/<slug:course_slug>/topics/<slug:topic_slug>/",
    #     views.topic_detail,
    #     name="topic_detail_in_collection",
    # ),
    # path("forms/<slug:form_slug>/", views.form_detail, name="form_detail"),
    # path(
    #     "collections/<slug:course_slug>/forms/<slug:form_slug>/",
    #     views.form_detail,
    #     name="form_detail_in_collection",
    # ),
    # path(
    #     "form_progress/<uuid:pk>/<int:page_number>/",
    #     views.form_fill_page,
    #     name="form_fill_page",
    # ),
    # path(
    #     "form_progress/<uuid:pk>/complete/",
    #     views.form_complete,
    #     name="form_complete",
    # ),
]
