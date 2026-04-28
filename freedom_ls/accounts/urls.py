from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path(
        "profile/",
        views.edit_profile,
        name="account_profile",
    ),
    path(
        "legal/<str:doc_type>/",
        views.legal_doc_view,
        name="legal_doc",
    ),
    path(
        "complete-registration/",
        views.complete_registration_view,
        name="complete_registration",
    ),
]
