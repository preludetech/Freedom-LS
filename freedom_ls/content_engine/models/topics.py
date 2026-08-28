from django.db import models
from django.urls import reverse

from freedom_ls.content_base.models import MarkdownContent, TitledContent
from freedom_ls.content_base.schema import ContentType as SchemaContentTypes


class Topic(TitledContent, MarkdownContent):
    """Topic content item."""

    CONTENT_TYPE = SchemaContentTypes.TOPIC

    category = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["site", "slug"], name="unique_topic_slug_per_site"
            )
        ]

    def preview_url(self):
        return reverse("content_engine:topic_detail", kwargs={"topic_slug": self.slug})


class Activity(TitledContent, MarkdownContent):
    """Topic content item."""

    CONTENT_TYPE = SchemaContentTypes.ACTIVITY

    category = models.CharField(max_length=200, blank=True, default="")
    level = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["site", "slug"], name="unique_activity_slug_per_site"
            )
        ]
        verbose_name_plural = "Activities"
