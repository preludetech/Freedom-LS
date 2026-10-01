from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render

from freedom_ls.content_engine.models import Article


def article_detail(request: HttpRequest, slug: str) -> HttpResponse:
    article = get_object_or_404(Article.objects.published(), slug=slug)
    return render(request, "blog/article_detail.html", {"article": article})
