from django.urls import path

from freedom_ls.feedback import views

app_name = "feedback"

urlpatterns = [
    path("form/<str:form_id>/", views.feedback_form_view, name="feedback_form"),
    path("submit/<str:form_id>/", views.feedback_submit_view, name="feedback_submit"),
    path(
        "dismiss/<str:form_id>/", views.feedback_dismiss_view, name="feedback_dismiss"
    ),
]
