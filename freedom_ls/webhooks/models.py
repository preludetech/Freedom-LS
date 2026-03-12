import secrets

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from freedom_ls.site_aware_models.models import SiteAwareModel
from freedom_ls.webhooks.registry import validate_event_type

STATUS_CHOICES = [
    ("pending", "Pending"),
    ("success", "Success"),
    ("failed", "Failed"),
    ("dead_letter", "Dead letter"),
]


class WebhookEndpoint(SiteAwareModel):
    url = models.URLField(max_length=2048)
    description = models.CharField(max_length=200)
    secret = models.CharField(max_length=64, editable=False)
    event_types = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)
    failure_count = models.PositiveIntegerField(default=0)
    disabled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.description

    def save(self, *args: object, **kwargs: object) -> None:
        if not self.secret:
            self.secret = secrets.token_urlsafe(48)
        super().save(*args, **kwargs)

    def clean(self) -> None:
        super().clean()
        # Validate event types against registry
        for event_type in self.event_types:
            try:
                validate_event_type(event_type)
            except ValueError as e:
                raise ValidationError({"event_types": str(e)}) from e

        # Enforce HTTPS when not in DEBUG mode
        if not settings.DEBUG and self.url and not self.url.startswith("https://"):
            raise ValidationError({"url": "Webhook URLs must use HTTPS in production."})


class WebhookEvent(SiteAwareModel):
    event_type = models.CharField(max_length=100)
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.event_type} at {self.created_at}"


class WebhookDelivery(SiteAwareModel):
    event = models.ForeignKey(
        WebhookEvent, on_delete=models.CASCADE, related_name="deliveries"
    )
    endpoint = models.ForeignKey(
        WebhookEndpoint, on_delete=models.CASCADE, related_name="deliveries"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    attempt_count = models.PositiveIntegerField(default=0)
    next_retry_at = models.DateTimeField(null=True, blank=True)
    last_status_code = models.PositiveIntegerField(null=True, blank=True)
    last_response_body = models.TextField(blank=True, default="")
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    last_latency_ms = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Webhook deliveries"

    def __str__(self) -> str:
        return f"Delivery {self.pk} ({self.status})"

    def save(self, *args: object, **kwargs: object) -> None:
        if len(self.last_response_body) > 500:
            self.last_response_body = self.last_response_body[:500]
        super().save(*args, **kwargs)
