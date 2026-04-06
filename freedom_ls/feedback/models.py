from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from freedom_ls.feedback.registry import is_valid_trigger_point
from freedom_ls.site_aware_models.models import SiteAwareModel


class FeedbackForm(SiteAwareModel):
    name = models.CharField(max_length=255)
    trigger_point = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    rating_label = models.CharField(max_length=255, default="How would you rate this?")
    text_prompt = models.CharField(
        max_length=255, blank=True, default="What could be improved?"
    )
    thank_you_message = models.CharField(
        max_length=255, default="Thanks for your feedback!"
    )
    min_occurrences = models.PositiveIntegerField(default=1)
    cooldown_days = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["site", "trigger_point"],
                condition=models.Q(is_active=True),
                name="unique_active_trigger_per_site",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if not is_valid_trigger_point(self.trigger_point):
            raise ValidationError(
                {"trigger_point": f"Unknown trigger point: {self.trigger_point}"}
            )

    def __str__(self) -> str:
        return self.name


class FeedbackTriggerLog(SiteAwareModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    trigger_point = models.CharField(max_length=100)
    count = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["site", "user", "trigger_point"],
                name="unique_trigger_log_per_user_site",
            )
        ]

    def __str__(self) -> str:
        return f"{self.user} - {self.trigger_point} ({self.count})"


class FeedbackResponse(SiteAwareModel):
    form = models.ForeignKey(
        FeedbackForm, on_delete=models.CASCADE, related_name="responses"
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=255)
    content_object = GenericForeignKey("content_type", "object_id")
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Feedback by {self.user} on {self.form.name} - {self.rating}/5"


class FeedbackDismissal(SiteAwareModel):
    form = models.ForeignKey(
        FeedbackForm, on_delete=models.CASCADE, related_name="dismissals"
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=255)
    content_object = GenericForeignKey("content_type", "object_id")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Dismissal by {self.user} on {self.form.name}"
