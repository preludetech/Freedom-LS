from django.urls import path

from freedom_ls.course_interest import views

app_name = "course_interest"

# Stub URL patterns registered in Phase 2 (Task 2.2) so that
# reverse("course_interest:express_interest", ...) resolves for the
# VisibilityEnforcingBackend's coming-soon CTA.
# TODO(Phase 3): flesh out these stubs into full HTMX views (Task 3.1).
urlpatterns = [
    path(
        "courses/<slug:course_slug>/express-interest/",
        views.partial_express_interest,
        name="express_interest",
    ),
    path(
        "courses/<slug:course_slug>/remove-interest/",
        views.partial_remove_interest,
        name="remove_interest",
    ),
]
