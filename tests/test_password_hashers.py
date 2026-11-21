"""Tests for the session-wide fast password hasher fixture in freedom_ls/conftest.py."""

import importlib

import pytest

from django.contrib.auth.hashers import check_password, get_hasher, make_password

from freedom_ls.accounts.factories import UserFactory


def test_get_hasher_by_default_is_md5() -> None:
    assert get_hasher().algorithm == "md5"


@pytest.mark.django_db
def test_user_factory_password_by_default_is_md5_hash(mock_site_context) -> None:
    user = UserFactory()

    assert user.password.startswith("md5$")


def test_argon2_hash_by_default_still_verifies() -> None:
    argon2_hash = make_password("a-password", hasher="argon2")

    assert check_password("a-password", argon2_hash) is True


@pytest.mark.parametrize("module_name", ["config.settings_base", "config.settings_dev"])
def test_settings_module_lists_argon2_first(module_name: str) -> None:
    """Reads the module attribute: `override_settings` changes only the live settings object."""
    module = importlib.import_module(module_name)

    assert (
        module.PASSWORD_HASHERS[0] == "django.contrib.auth.hashers.Argon2PasswordHasher"
    )
