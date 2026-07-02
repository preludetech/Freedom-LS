from django.urls import path

from freedom_ls.course_interest import views

app_name = "course_interest"

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
