from django.urls import path

from . import views

app_name = "course_applications"

urlpatterns = [
    path("apply/<slug:course_slug>/", views.apply, name="apply"),
    path("status/<uuid:pk>/", views.application_status, name="status"),
]
