from __future__ import annotations

from typing import cast

from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from freedom_ls.content_base.models import MarkdownContent, TitledContent
from freedom_ls.content_base.schema import ContentType as SchemaContentTypes
from freedom_ls.content_engine.config import config
from freedom_ls.site_aware_models.models import SiteAwareManager


class ArticleVisibility(models.TextChoices):
    PUBLISHED = "published", _("Published")
    HIDDEN = "hidden", _("Hidden")


class ArticleQuerySet(models.QuerySet["Article"]):
    def published(self) -> ArticleQuerySet:
        return self.filter(visibility=ArticleVisibility.PUBLISHED)


class ArticleManager(SiteAwareManager):
    # Hand-written pass-through, the way comms.NotificationManager does it,
    # because SiteAwareManager.from_queryset() is not a base mypy can resolve.
    _queryset_class = ArticleQuerySet

    def published(self) -> ArticleQuerySet:
        return cast("ArticleQuerySet", self.get_queryset()).published()


class Article(TitledContent, MarkdownContent):
    """A standalone markdown page that belongs to no course and is publicly readable."""

    CONTENT_TYPE = SchemaContentTypes.ARTICLE

    published_on = models.DateField()
    author = models.CharField(max_length=200, blank=True)
    visibility = models.CharField(
        max_length=20,
        choices=ArticleVisibility.choices,
        default=ArticleVisibility.PUBLISHED,
        db_index=True,
    )
    show_date = models.BooleanField(null=True)
    show_author = models.BooleanField(null=True)

    objects = ArticleManager()

    class Meta:
        ordering = ["-published_on", "slug"]
        constraints = [
            models.UniqueConstraint(
                fields=["site", "slug"], name="unique_article_slug_per_site"
            )
        ]

    def get_absolute_url(self) -> str:
        return reverse("blog:article_detail", kwargs={"slug": self.slug})

    @property
    def shows_date(self) -> bool:
        return config.ARTICLE_SHOW_DATE if self.show_date is None else self.show_date

    @property
    def shows_author(self) -> bool:
        if not self.author:
            return False
        return (
            config.ARTICLE_SHOW_AUTHOR if self.show_author is None else self.show_author
        )
