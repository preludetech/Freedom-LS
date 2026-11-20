"""Tests for the Personal details section config."""

from __future__ import annotations

from typing import cast

import pytest

from django.contrib.sites.models import Site
from django.http import Http404, HttpRequest
from django.test import RequestFactory

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.accounts.panels.personal_details.actions import (
    ACCOUNT_CAPABILITIES,
    CHANGE_OWN_EMAIL_ADDRESSES,
    CHANGE_OWN_NAME,
    CHANGE_OWN_PASSWORD,
    CHANGE_OWN_PROFILE_PICTURE,
    REMOVE_OWN_PROFILE_PICTURE,
)
from freedom_ls.accounts.panels.personal_details.config import PersonalDetailsConfig

pytestmark = pytest.mark.django_db


@pytest.fixture
def user(mock_site_context: Site) -> User:
    return cast(User, UserFactory())


@pytest.fixture
def request_for(rf: RequestFactory, user: User) -> HttpRequest:
    request = rf.get("/accounts/profile/personal-details")
    request.user = user
    return request


def test_get_object_returns_the_signed_in_users_row(request_for, user):
    assert PersonalDetailsConfig.get_object(request_for).pk == user.pk


def test_authorise_instance_passes_for_the_users_own_row(request_for, user):
    PersonalDetailsConfig.authorise_instance(request_for, user)


def test_authorise_instance_is_a_404_for_another_users_row(request_for):
    with pytest.raises(Http404):
        PersonalDetailsConfig.authorise_instance(request_for, UserFactory())


def test_the_capabilities_are_the_own_account_names():
    assert {
        CHANGE_OWN_NAME,
        CHANGE_OWN_PROFILE_PICTURE,
        REMOVE_OWN_PROFILE_PICTURE,
        CHANGE_OWN_EMAIL_ADDRESSES,
        CHANGE_OWN_PASSWORD,
    } == ACCOUNT_CAPABILITIES


@pytest.mark.parametrize(
    "capability",
    [
        CHANGE_OWN_NAME,
        CHANGE_OWN_PROFILE_PICTURE,
        REMOVE_OWN_PROFILE_PICTURE,
        CHANGE_OWN_EMAIL_ADDRESSES,
        CHANGE_OWN_PASSWORD,
    ],
)
def test_has_capability_grants_each_name_on_the_users_own_row(
    request_for, user, capability
):
    assert PersonalDetailsConfig.has_capability(request_for, capability, user)


@pytest.mark.parametrize(
    "capability",
    [CHANGE_OWN_NAME, CHANGE_OWN_PROFILE_PICTURE, REMOVE_OWN_PROFILE_PICTURE],
)
def test_has_capability_denies_each_name_on_another_users_row(request_for, capability):
    assert not PersonalDetailsConfig.has_capability(
        request_for, capability, UserFactory()
    )


def test_has_capability_denies_the_django_change_permission(request_for, user):
    assert not PersonalDetailsConfig.has_capability(
        request_for, "accounts.change_user", user
    )


def test_get_instance_label_is_personal_details(user):
    assert PersonalDetailsConfig.get_instance_label(user) == "Personal details"
