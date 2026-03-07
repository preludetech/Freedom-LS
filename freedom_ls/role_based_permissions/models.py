from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from freedom_ls.site_aware_models.models import SiteAwareModel


class SystemRoleAssignment(models.Model):
    """Assigns a system-wide role to a user (not site-specific).

    Uses BigAutoField (not UUIDField) because this intentionally does not
    extend SiteAwareModel — system roles are global, not site-scoped.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="system_roles",
    )
    role = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "role"], name="unique_system_role_per_user"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user} - {self.role}"


class SiteRoleAssignment(SiteAwareModel):
    """Assigns a site-scoped role to a user."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="site_roles",
    )
    role = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "site", "role"], name="unique_site_role_per_user"
            ),
        ]
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["site", "role"]),
        ]

    def __str__(self) -> str:
        return f"{self.user} - {self.role}"


class ObjectRoleAssignment(SiteAwareModel):
    """Assigns a role to a user scoped to a specific object (e.g. a Course)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="object_role_assignments",
    )
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
    )
    object_id = models.CharField(max_length=255)
    target = GenericForeignKey("content_type", "object_id")
    role = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "content_type", "object_id", "role"],
                name="unique_object_role_per_user",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["content_type", "object_id", "role", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.user} - {self.role} on {self.target}"
