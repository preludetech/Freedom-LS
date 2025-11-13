from django.db import models
from site_aware_models.models import SiteAwareModel
import secrets


class Client(SiteAwareModel):
    """
    Client model for API authentication.
    Use to allow other applications to authenticate and use an API exposed here.
    """

    name = models.CharField(max_length=200, help_text="Client application name")
    api_key = models.CharField(
        max_length=64,
        unique=True,
        help_text="API key for authentication",
        editable=False,
    )
    is_active = models.BooleanField(
        default=True, help_text="Whether this client is active"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "API Client"
        verbose_name_plural = "API Clients"

    def __str__(self):
        return f"{self.name} ({'Active' if self.is_active else 'Inactive'})"

    def save(self, *args, **kwargs):
        """Generate API key on first save."""
        if not self.api_key:
            self.api_key = self.generate_api_key()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_api_key():
        """Generate a secure random API key."""
        return secrets.token_urlsafe(48)
