from django.db import models
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.contrib.sites.shortcuts import get_current_site
from freedom_ls.site_aware_models.models import _thread_locals, SiteAwareModelBase, SiteAwareModel


class UserManager(BaseUserManager):
    def get_queryset(self):
        queryset = super().get_queryset()
        request = getattr(_thread_locals, "request", None)
        if request:
            site = get_current_site(request)
            return queryset.filter(site_id=site)
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

    first_name = models.CharField(null=True, max_length=200)
    last_name = models.CharField(null=True, max_length=200)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    # The fields required when user is created. Email and password are required by default
    REQUIRED_FIELDS = []

    objects = UserManager()

    @property
    def username(self) -> str:
        """Return email as username for template compatibility."""
        return self.email


class SiteSignupPolicy(SiteAwareModel):
    """
    Per-site toggle for whether self-service account signups are allowed.
    If no row exists for a site, the global default in settings.ALLOW_SIGN_UPS is used.
    """

    allow_signups = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["site"], name="unique_signup_policy_per_site"),
        ]

    def __str__(self):
        return f"{self.site.domain}: allow_signups={self.allow_signups}"


# class SiteGroup(SiteAwareModelBase, AuthGroup):
#     """Custom Group model with site awareness"""

#     group_name  = models.CharField(null=True, max_length=200)
#     class Meta:
#         verbose_name = _("group")
#         verbose_name_plural = _("groups")
#         unique_together = [['site_id', 'group_name']]

#     def __str__(self):
#         return self.group_name
