from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render

from freedom_ls.blog.config import config
from freedom_ls.content_engine.models import Article


def article_detail(request: HttpRequest, slug: str) -> HttpResponse:
    article = get_object_or_404(Article.objects.published(), slug=slug)
    meta_description = article.description or article.subtitle or article.title
    image_file = article.image_file
    # Crawlers fetch og:image with no page to resolve a relative path against.
    og_image_url = request.build_absolute_uri(image_file.file.url) if image_file else ""
    return render(
        request,
        "blog/article_detail.html",
        {
            "article": article,
            "meta_description": meta_description,
            "blog_name": config.BLOG_NAME,
            "image_file": image_file,
            "og_image_url": og_image_url,
        },
    )


def article_list(request: HttpRequest) -> HttpResponse:
    articles = Article.objects.published()
    return render(
        request,
        "blog/article_list.html",
        {"articles": articles, "blog_name": config.BLOG_NAME},
    )
