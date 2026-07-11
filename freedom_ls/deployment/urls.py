from django.urls import path

from freedom_ls.deployment import views

app_name = "deployment"

urlpatterns = [
    path("sentry-debug/", views.trigger_error, name="trigger_error"),
]
