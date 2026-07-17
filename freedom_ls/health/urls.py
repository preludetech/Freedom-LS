from django.urls import path

from freedom_ls.health import views

app_name = "health"

urlpatterns = [
    path("liveness/", views.liveness, name="liveness"),
    path("readiness/", views.ReadinessView.as_view(), name="readiness"),
]
