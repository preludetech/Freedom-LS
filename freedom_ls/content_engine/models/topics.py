from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import models
from django.urls import reverse

from freedom_ls.content_base.models import MarkdownContent, TitledContent
from freedom_ls.content_base.schema import ContentType as SchemaContentTypes

if TYPE_CHECKING:
    from freedom_ls.content_engine.models.question_sections import FormQuestionTopic
    from freedom_ls.form_engine.models import FormQuestion


class Topic(TitledContent, MarkdownContent):
    """Topic content item."""

    CONTENT_TYPE = SchemaContentTypes.TOPIC

    category = models.CharField(max_length=200, blank=True, default="")
    testing_questions: models.ManyToManyField[FormQuestion, FormQuestionTopic] = (
        models.ManyToManyField(
            "freedom_ls_form_engine.FormQuestion",
            through="FormQuestionTopic",
            blank=True,
            related_name="topics",
        )
    )

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
