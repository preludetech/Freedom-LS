"""Tests for accounts factories."""

import pytest
from django.contrib.sites.models import Site

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User


@pytest.mark.django_db
class TestUserFactory:
    def test_user_factory_creates_user(self, mock_site_context: Site) -> None:
        """UserFactory creates a user with a hashed password matching their email."""
        user = UserFactory()
        assert isinstance(user, User)
        assert user.pk is not None
        assert user.email
        assert user.is_active is True
        assert user.is_staff is False
        assert user.is_superuser is False
        assert user.check_password(user.email)

    def test_user_factory_staff_trait(self, mock_site_context: Site) -> None:
        """The staff trait sets is_staff=True."""
        user = UserFactory(staff=True)
        assert user.is_staff is True
        assert user.is_superuser is False

    def test_user_factory_superuser_trait(self, mock_site_context: Site) -> None:
        """The superuser trait sets both is_staff and is_superuser."""
        user = UserFactory(superuser=True)
        assert user.is_staff is True
        assert user.is_superuser is True

    def test_user_factory_site_from_context(self, mock_site_context: Site) -> None:
        """Site is automatically set from the mock_site_context fixture."""
        user = UserFactory()
        assert user.site == mock_site_context

    def test_user_factory_custom_password(self, mock_site_context: Site) -> None:
        """A custom password can be provided and is properly hashed."""
        user = UserFactory(password="custom")
        assert user.check_password("custom")
        assert not user.check_password(user.email)
