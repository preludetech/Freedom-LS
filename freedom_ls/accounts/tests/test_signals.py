"""Signal receivers: EmailAddress changes move updated_at; deleting a user removes their picture."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from allauth.account.models import EmailAddress

from django.contrib.auth.models import update_last_login
from django.db import transaction

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.tests.factories import SiteFactory
from freedom_ls.tests.site_context import drop_ambient_request, site_context

pytestmark = pytest.mark.django_db

LONG_AGO = datetime(2020, 1, 1, tzinfo=UTC)


def _create_verified(user: User) -> None:
    EmailAddress.objects.create(
        user=user, email=user.email, verified=True, primary=True
    )


def _flip_to_unverified(user: User) -> None:
    address = EmailAddress.objects.create(
        user=user, email=user.email, verified=True, primary=True
    )
    _age(user)
    address.verified = False
    address.save()


def _flip_to_verified(user: User) -> None:
    address = EmailAddress.objects.create(
        user=user, email=user.email, verified=False, primary=True
    )
    _age(user)
    address.verified = True
    address.save()


def _delete_address(user: User) -> None:
    address = EmailAddress.objects.create(
        user=user, email=user.email, verified=True, primary=True
    )
    _age(user)
    address.delete()


def _age(user: User) -> None:
    User._base_manager.filter(pk=user.pk).update(updated_at=LONG_AGO)


def _updated_at(user: User) -> datetime:
    return User._base_manager.get(pk=user.pk).updated_at


def _delete_then_fail(user: User) -> None:
    with transaction.atomic():
        user.delete()
        raise RuntimeError("roll back")


CHANGES: list[Callable[[User], None]] = [
    _create_verified,
    _flip_to_unverified,
    _flip_to_verified,
    _delete_address,
]


@pytest.fixture
def user(mock_site_context) -> User:
    created: User = UserFactory()
    _age(created)
    return created


@pytest.mark.parametrize("change", CHANGES, ids=lambda fn: fn.__name__)
def test_an_email_address_change_moves_updated_at(user, change):
    change(user)

    assert _updated_at(user) > LONG_AGO


@pytest.mark.parametrize("change", CHANGES, ids=lambda fn: fn.__name__)
def test_updated_at_moves_with_no_request(user, change):
    drop_ambient_request()

    change(user)

    assert _updated_at(user) > LONG_AGO


@pytest.mark.parametrize("change", CHANGES, ids=lambda fn: fn.__name__)
def test_updated_at_moves_under_a_request_for_another_host(user, change):
    with site_context(SiteFactory(domain="other.example.com")):
        change(user)

    assert _updated_at(user) > LONG_AGO


def test_a_login_does_not_move_updated_at(user):
    update_last_login(User, user)

    assert _updated_at(user) == LONG_AGO


class TestProfilePictureDeletion:
    def test_deleting_a_user_removes_the_file_on_commit(
        self, mock_site_context, django_capture_on_commit_callbacks
    ):
        user = UserFactory(with_profile_picture=True)
        storage, name = user.profile_picture.storage, user.profile_picture.name
        assert storage.exists(name)

        with django_capture_on_commit_callbacks(execute=True):
            user.delete()

        assert not storage.exists(name)

    def test_a_queryset_delete_removes_the_file(
        self, mock_site_context, django_capture_on_commit_callbacks
    ):
        user = UserFactory(with_profile_picture=True)
        storage, name = user.profile_picture.storage, user.profile_picture.name

        with django_capture_on_commit_callbacks(execute=True):
            User._base_manager.filter(pk=user.pk).delete()

        assert not storage.exists(name)

    def test_a_rolled_back_delete_leaves_the_file_and_the_row(
        self, mock_site_context, django_capture_on_commit_callbacks
    ):
        user = UserFactory(with_profile_picture=True)
        storage, name = user.profile_picture.storage, user.profile_picture.name
        pk = user.pk

        with (
            django_capture_on_commit_callbacks(execute=True),
            pytest.raises(RuntimeError),
        ):
            _delete_then_fail(user)

        assert storage.exists(name)
        assert User._base_manager.filter(pk=pk).exists()

    def test_deleting_a_user_without_a_picture_does_nothing(
        self, mock_site_context, django_capture_on_commit_callbacks
    ):
        user = UserFactory()

        with django_capture_on_commit_callbacks(execute=True) as callbacks:
            user.delete()

        assert callbacks == []

    def test_a_deactivated_user_keeps_the_picture(
        self, mock_site_context, django_capture_on_commit_callbacks
    ):
        user = UserFactory(with_profile_picture=True)
        storage, name = user.profile_picture.storage, user.profile_picture.name

        with django_capture_on_commit_callbacks(execute=True):
            user.is_active = False
            user.save()

        user.refresh_from_db()
        assert user.profile_picture.name == name
        assert storage.exists(name)
