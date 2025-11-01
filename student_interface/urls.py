from django.urls import path
from . import views

app_name = "student_interface"

urlpatterns = [
    path("topics/<uuid:pk>/", views.topic_detail, name="topic_detail"),
    path("forms/<uuid:pk>/", views.form_detail, name="form_detail"),
    path("forms/<uuid:pk>/start/", views.form_start, name="form_start"),
    path("form_progress/<uuid:pk>/<int:page_number>/", views.form_fill_page, name="form_fill_page"),
]
