from django.db import models
from system_base.models import SiteAwareModel


class ContentItem(SiteAwareModel):
    title = models.CharField(max_length=150)
    blurb = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.title


class ContentSequence(SiteAwareModel):
    """An ordered list of contentItems"""

    title = models.CharField(max_length=150)
    blurb = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.title


class ContentSequenceItem(SiteAwareModel):
    """Through model for ordering ContentItems within a ContentSequence"""

    content_sequence = models.ForeignKey(ContentSequence, on_delete=models.CASCADE)
    content_item = models.ForeignKey(ContentItem, on_delete=models.CASCADE)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]
        constraints = [
            models.UniqueConstraint(
                fields=["content_sequence", "content_item"],
                name="unique_content_item_per_sequence",
            )
        ]

    def __str__(self):
        return f"{self.content_sequence.title}: {self.order}. {self.content_item.title}"
