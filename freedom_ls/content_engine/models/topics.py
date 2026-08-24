from django.db import models
from django.urls import reverse

from ..schema import ContentType as SchemaContentTypes
from .base import MarkdownContent, TitledContent


class Topic(TitledContent, MarkdownContent):
    """Topic content item."""

    CONTENT_TYPE = SchemaContentTypes.TOPIC

    category = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        unique_together = ["site", "slug"]

    def preview_url(self):
        return reverse("content_engine:topic_detail", kwargs={"topic_slug": self.slug})


class Activity(TitledContent, MarkdownContent):
    """Topic content item."""

    CONTENT_TYPE = SchemaContentTypes.ACTIVITY

    category = models.CharField(max_length=200, blank=True, default="")
    level = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        unique_together = ["site", "slug"]
        verbose_name_plural = "Activities"
