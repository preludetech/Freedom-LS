from __future__ import annotations

from typing import Any

from django.conf import settings
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.contrib.sites.models import Site
from django.db import models

from freedom_ls.site_aware_models.models import (
    SiteAwareModel,
    SiteAwareModelBase,
    _thread_locals,
    get_cached_site,
)


class UserManager(BaseUserManager["User"]):
    def get_queryset(self):
        queryset = super().get_queryset()
        request = getattr(_thread_locals, "request", None)
        if request:
            site = get_cached_site(request)
            if isinstance(site, Site):
                return queryset.filter(site=site)
        return queryset

    def create_user(
        self,
        email,
        password=None,
        is_active=True,
        is_staff=False,
        is_admin=False,
    ):
        if not email:
            raise ValueError("User must have an email address")
        if not password:
            raise ValueError("User must have a password")

        user_obj = self.model(
            email=self.normalize_email(email),
        )
        user_obj.set_password(password)
        user_obj.is_staff = is_staff
        user_obj.is_superuser = is_admin
        user_obj.is_active = is_active
        user_obj.save(using=self.db)
        return user_obj

    def create_superuser(self, email, password=None):
        user = self.create_user(
            email,
            password=password,
            is_staff=True,
            is_admin=True,
        )
        return user


class User(SiteAwareModelBase, AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)

    first_name = models.CharField(blank=True, default="", max_length=200)
    last_name = models.CharField(blank=True, default="", max_length=200)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    # The fields required when user is created. Email and password are required by default
    REQUIRED_FIELDS = []

    objects: models.Manager = UserManager()

    @property
    def username(self) -> str:
        """Return email as username for template compatibility."""
        return self.email

    @property
    def display_name(self):
        return self.first_name or self.email


class SiteSignupPolicy(SiteAwareModel):
    """
    Per-site signup policy — controls whether signups are allowed and what
    information is collected from the user at signup / post-verification.
    If no row exists for a site, the global default in settings.ALLOW_SIGN_UPS
    is used for `allow_signups`; the other fields use their model defaults.
    """

    allow_signups = models.BooleanField(default=True)
    require_name = models.BooleanField(default=True)
    require_terms_acceptance = models.BooleanField(default=False)
    additional_registration_forms = models.JSONField(default=list, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["site"], name="unique_signup_policy_per_site"
            ),
        ]

    def __str__(self):
        return f"{self.site.domain}: allow_signups={self.allow_signups}"


class LegalConsent(SiteAwareModel):
    """Append-only record of a user's consent to a legal document.

    Each row is created exactly once (at signup, or via a future re-consent
    flow). The model rejects updates to existing rows; the admin registers
    this model as fully read-only.
    """

    DOCUMENT_TYPE_CHOICES = [("terms", "Terms"), ("privacy", "Privacy")]
    CONSENT_METHOD_CHOICES = [
        ("signup_checkbox", "Signup checkbox"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="legal_consents",
    )
    document_type = models.CharField(max_length=16, choices=DOCUMENT_TYPE_CHOICES)
    document_version = models.CharField(max_length=64)
    git_hash = models.CharField(max_length=64)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    consent_method = models.CharField(
        max_length=32,
        choices=CONSENT_METHOD_CHOICES,
        default="signup_checkbox",
    )

    class Meta:
        indexes = [models.Index(fields=["user", "document_type"])]
        ordering = ["-timestamp"]

    def save(self, *args: Any, **kwargs: Any) -> None:
        # `SiteAwareModel` uses a UUID PK with `default=uuid.uuid4`, so
        # `self.pk` is set as soon as the instance is constructed — before
        # the row exists in the DB. We therefore need `_state.adding` to
        # distinguish "first-time insert" from "update an existing row".
        # Note: this guard only covers ``.save()``. ``QuerySet.update()`` and
        # ``bulk_update()`` bypass it silently — the admin is registered as
        # fully read-only as the second layer of defence.
        if self.pk is not None and self._state.adding is False:
            raise ValueError(
                "LegalConsent records are append-only and cannot be updated"
            )
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return (
            f"{self.user_id} accepted {self.document_type} "
            f"v{self.document_version} at {self.timestamp:%Y-%m-%d %H:%M}"
        )


# class SiteGroup(SiteAwareModelBase, AuthGroup):
#     """Custom Group model with site awareness"""

#     group_name  = models.CharField(null=True, max_length=200)
#     class Meta:
#         verbose_name = _("group")
#         verbose_name_plural = _("groups")
#         unique_together = [['site_id', 'group_name']]

#     def __str__(self):
#         return self.group_name
