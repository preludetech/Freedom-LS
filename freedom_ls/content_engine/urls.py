from django.urls import path

from freedom_ls.content_engine import views

app_name = "content_engine"

urlpatterns = [
    path("audio/<uuid:pk>/", views.audio_file, name="audio_file"),
]
