from django.urls import path
from . import views

app_name = "educator_interface"

urlpatterns = [
    path("", views.home, name="home"),
    path("cohorts", views.cohorts_list, name="cohorts_list"),
    path("courses/", views.course_list, name="course_list"),
    path(
        "courses/<slug:course_slug>/progress/",
        views.course_student_progress,
        name="course_student_progress",
    ),
]
