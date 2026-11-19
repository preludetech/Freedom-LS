from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path(
        "profile/",
        views.account_area,
        name="account_profile",
    ),
    # Before the catch-all, which would otherwise match it.
    path(
        "profile/picture/",
        views.edit_profile_picture,
        name="account_profile_picture",
    ),
    path(
        "profile/<path:path_string>",
        views.account_area,
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
