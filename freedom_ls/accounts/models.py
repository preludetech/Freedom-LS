from django.db import models
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
    Group as AuthGroup,
)
from django.contrib.sites.shortcuts import get_current_site
from django.utils.translation import gettext_lazy as _
from freedom_ls.site_aware_models.models import _thread_locals, SiteAwareModelBase, SiteAwareModel, SiteAwareManager
from guardian.mixins import GuardianUserMixin, GuardianGroupMixin
from guardian.models import GroupObjectPermissionAbstract


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


class SiteGroup(SiteAwareModelBase, AuthGroup, GuardianGroupMixin):
    """Custom Group model with site awareness."""
    group_name = models.CharField(max_length=200, blank=False)

    # Explicitly declare manager to ensure it's not overridden by Django MTI
    objects = SiteAwareManager()

    class Meta:
        verbose_name = _("group")
        verbose_name_plural = _("groups")
        unique_together = [['site_id', 'group_name']]

    def __str__(self):
        return self.group_name

    def save(self, *args, **kwargs):
        """Auto-generate the name field from group_name and site."""
        if not self.site_id:
            request = getattr(_thread_locals, "request", None)
            if request:
                self.site = get_current_site(request)

        # Auto-generate the 'name' field for Django's Group compatibility
        if self.site_id:
            self.name = f"{self.group_name} ({self.site.domain})"

        super().save(*args, **kwargs)



class SiteGroupPermissionsMixin(PermissionsMixin):
    """
    This mixin overrides the 'groups' field from PermissionsMixin.
    We need this because the default PermissionsMixin hardcodes the relationship
    to 'auth.Group', but we need it to point to 'SiteGroup'.
    """
    groups = models.ManyToManyField(
        SiteGroup,  # Pointing to our new custom model
        verbose_name=_("groups"),
        blank=True,
        help_text=_(
            "The groups this user belongs to. A user will get all permissions "
            "granted to each of their groups."
        ),
        related_name="user_set",
        related_query_name="user",
    )

    class Meta:
        abstract = True


class User(SiteAwareModelBase, AbstractBaseUser, SiteGroupPermissionsMixin, GuardianUserMixin):
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


class SiteGroupObjectPermission(GroupObjectPermissionAbstract):
    """
    Guardian needs a custom table to store object permissions for our custom Group.
    """
    group = models.ForeignKey(SiteGroup, on_delete=models.CASCADE)

    class Meta(GroupObjectPermissionAbstract.Meta):
        abstract = False


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
