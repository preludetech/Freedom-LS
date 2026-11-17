"""The smallest user model a host project can give the framework."""

from __future__ import annotations

from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.contrib.sites.models import Site
from django.db import models


class UserManager(BaseUserManager["User"]):
    def create_user(
        self, email: str, password: str | None = None, **extra_fields: object
    ) -> User:
        user = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    # A host's user model usually records its site; tests that build a user
    # for a specific site pass it here.
    site = models.ForeignKey(Site, null=True, blank=True, on_delete=models.SET_NULL)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    objects = UserManager()
