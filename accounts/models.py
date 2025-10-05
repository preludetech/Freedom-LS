from django.db import models
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
    Permission,
)
from django.contrib.sites.models import Site
from django.contrib.sites.shortcuts import get_current_site
import uuid
from system_base.models import _thread_locals, SiteAwareModel
from django.utils.translation import gettext_lazy as _


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


class User(SiteAwareModel, AbstractBaseUser, PermissionsMixin):
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


# class SiteGroup(SiteAwareModel):
#     """Custom Group model with site awareness"""

#     name = models.CharField(max_length=150)

#     permissions = models.ManyToManyField(
#         Permission,
#         verbose_name=_("permissions"),
#         blank=True,
#     )

#     class Meta:
#         verbose_name = _("group")
#         verbose_name_plural = _("groups")
#         constraints = [
#             models.UniqueConstraint(
#                 fields=["site_id", "name"], name="unique_group_name_per_site"
#             )
#         ]

#     def __str__(self):
#         return self.name
