from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render

from freedom_ls.blog.config import config
from freedom_ls.content_engine.models import Article


def article_detail(request: HttpRequest, slug: str) -> HttpResponse:
    article = get_object_or_404(Article.objects.published(), slug=slug)
    meta_description = article.description or article.subtitle or article.title
    return render(
        request,
        "blog/article_detail.html",
        {
            "article": article,
            "meta_description": meta_description,
            "blog_name": config.BLOG_NAME,
        },
    )


def article_list(request: HttpRequest) -> HttpResponse:
    articles = Article.objects.published()
    return render(
        request,
        "blog/article_list.html",
        {"articles": articles, "blog_name": config.BLOG_NAME},
    )
