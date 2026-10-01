from django.urls import path

from freedom_ls.blog import views

app_name = "blog"

urlpatterns = [
    path("", views.article_list, name="index"),
    path("<slug:slug>/", views.article_detail, name="article_detail"),
]
