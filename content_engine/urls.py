from django.urls import path
from . import views

app_name = "content_engine"


# TODO: Use slugs instead of uuids for topics, collections and forms
# slugs should be generated against the titles of the different things

urlpatterns = [
    path("topics/<uuid:pk>/", views.topic_detail, name="topic_detail"),
    path("collections/<uuid:pk>/", views.collection_detail, name="collection_detail"),
    path("forms/<uuid:pk>/", views.form_detail, name="form_detail"),
    path("form-pages/<uuid:pk>/", views.form_page_detail, name="form_page_detail"),
]
