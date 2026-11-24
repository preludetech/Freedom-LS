from django.urls import path

from . import views

app_name = "learner_interface"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("courses/", views.all_courses, name="courses"),
    path(
        "courses/<slug:course_slug>/detail/",
        views.course_detail,
        name="course_detail",
    ),
    path("courses/<slug:course_slug>/", views.course_home, name="course_home"),
    path(
        "courses/<slug:course_slug>/access/",
        views.initiate_course_access,
        name="initiate_course_access",
    ),
    path(
        "courses/<slug:course_slug>/reference/",
        views.course_reference,
        name="course_reference",
    ),
    path(
        "courses/<slug:course_slug>/reference/<slug:part_slug>/<slug:topic_slug>/",
        views.course_reference_topic,
        name="course_reference_topic",
    ),
    path(
        "courses/<slug:course_slug>/revision/",
        views.course_revision,
        name="course_revision",
    ),
    path(
        "courses/<slug:course_slug>/revision/start/",
        views.course_revision_start,
        name="course_revision_start",
    ),
    path(
        "courses/<slug:course_slug>/revision/answer/",
        views.partial_course_revision_answer,
        name="course_revision_answer",
    ),
    path(
        "courses/<slug:course_slug>/revision/next/",
        views.partial_course_revision_next,
        name="course_revision_next",
    ),
    path(
        "courses/<slug:course_slug>/revision/guessed/",
        views.partial_course_revision_guessed,
        name="course_revision_guessed",
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
        "courses/<slug:course_slug>/<int:index>/declaration",
        views.form_declaration,
        name="form_declaration",
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
        "courses/<slug:course_slug>/<int:index>/submit-and-exit",
        views.form_submit_and_exit,
        name="form_submit_and_exit",
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
