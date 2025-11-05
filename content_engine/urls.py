from django.urls import path
from . import views

app_name = "content_engine"

urlpatterns = [
    path("topics/<slug:topic_slug>/", views.topic_detail, name="topic_detail"),
    path(
        "collections/<slug:collection_slug>/",
        views.collection_detail,
        name="collection_detail",
    ),
    path("forms/<slug:form_slug>/", views.form_detail, name="form_detail"),
    path("form-pages/<uuid:pk>/", views.form_page_detail, name="form_page_detail"),
]
