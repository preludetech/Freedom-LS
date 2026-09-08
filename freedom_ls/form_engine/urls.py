from django.urls import path

from freedom_ls.form_engine import views

app_name = "form_engine"

urlpatterns = [
    path(
        "progress/<uuid:progress_pk>/question/<uuid:question_pk>/file/upload/",
        views.partial_question_file_upload,
        name="question_file_upload",
    ),
    path(
        "progress/<uuid:progress_pk>/question/<uuid:question_pk>/file/remove/",
        views.partial_question_file_remove,
        name="question_file_remove",
    ),
    path(
        "answer-file/<uuid:file_pk>/",
        views.own_question_answer_file,
        name="own_question_answer_file",
    ),
]
