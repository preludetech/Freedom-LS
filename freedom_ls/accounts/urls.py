from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    # allauth's email and change-password pages are panels on Personal
    # details now. These answer first only where this URLconf is included
    # before allauth.urls; allauth's own URL names still reverse to the same
    # paths. allauth's set-password page stays: flows such as an application
    # claim send a user there with a `next` to return to.
    path("email/", views.personal_details_redirect),
    path("password/change/", views.personal_details_redirect),
    path(
        "profile/",
        views.account_area,
        name="account_profile",
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
