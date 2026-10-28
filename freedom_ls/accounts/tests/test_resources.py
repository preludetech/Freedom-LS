"""Tests for the CSV export on the user admin."""

from __future__ import annotations

import csv
import io

import pytest
from allauth.account.models import EmailAddress

from django.contrib.auth.models import Permission
from django.http import HttpResponse
from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import EmailAddressFactory, UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.accounts.resources import USER_EXPORT_FIELDS, UserResource

APP_LABEL = "freedom_ls_accounts"


@pytest.fixture
def staff_client(mock_site_context, db):
    """Staff user with permission to view users."""
    user = UserFactory(staff=True)
    permission = Permission.objects.get(
        content_type__app_label=APP_LABEL, codename="view_user"
    )
    user.user_permissions.add(permission)
    client = Client()
    client.force_login(user)
    return client


@pytest.fixture
def unprivileged_staff_client(mock_site_context, db):
    """Staff user with no permission on any accounts model."""
    user = UserFactory(staff=True)
    client = Client()
    client.force_login(user)
    return client


def _export_selected(
    client: Client, model_name: str, pks: list[str], query: str = ""
) -> HttpResponse:
    response: HttpResponse = client.post(
        reverse(f"admin:{APP_LABEL}_{model_name}_changelist") + query,
        {
            "action": "export_admin_action",
            "select_across": "1",
            "index": "0",
            "_selected_action": pks,
        },
    )
    return response


def _rows(response: HttpResponse) -> tuple[list[str], list[list[str]]]:
    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
    return rows[0], rows[1:]


def _cell(response: HttpResponse, user: User, column: str) -> str:
    """The value in `column` of the row exported for `user`."""
    header, rows = _rows(response)
    (row,) = [r for r in rows if r[header.index("email")] == user.email]
    return row[header.index(column)]


def _export_user(client: Client, user: User) -> HttpResponse:
    return _export_selected(client, "user", [str(user.pk)])


@pytest.mark.django_db
def test_export_header_is_the_whitelisted_columns_in_order(staff_client):
    user = UserFactory()

    response = _export_user(staff_client, user)

    header, _ = _rows(response)
    assert header == list(USER_EXPORT_FIELDS)


@pytest.mark.django_db
def test_export_body_never_contains_the_password_or_its_hash(staff_client):
    user = UserFactory()

    response = _export_user(staff_client, user)

    body = response.content.decode("utf-8-sig")
    assert "password" not in body
    assert user.password not in body


@pytest.mark.django_db
def test_email_verified_is_true_for_a_verified_address(staff_client):
    user = UserFactory()
    EmailAddressFactory(user=user)

    response = _export_user(staff_client, user)

    assert _cell(response, user, "email_verified") == "TRUE"


@pytest.mark.django_db
def test_email_verified_matches_the_address_ignoring_case(staff_client):
    user = UserFactory(email="Mixed.Case@example.com")
    EmailAddressFactory(user=user, email="mixed.case@example.com")

    response = _export_user(staff_client, user)

    assert _cell(response, user, "email_verified") == "TRUE"


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("verified", "other_address"),
    [(False, False), (True, True)],
    ids=["unverified_address", "verified_different_address"],
)
def test_email_verified_is_false_without_a_verified_matching_address(
    staff_client, verified, other_address
):
    user = UserFactory()
    EmailAddressFactory(
        user=user,
        verified=verified,
        email="elsewhere@example.com" if other_address else user.email,
    )

    response = _export_user(staff_client, user)

    assert _cell(response, user, "email_verified") == "FALSE"


@pytest.mark.django_db
def test_email_verified_is_false_for_a_user_with_no_address_rows(staff_client):
    user = UserFactory()
    assert not EmailAddress.objects.filter(user=user).exists()

    response = _export_user(staff_client, user)

    assert _cell(response, user, "email_verified") == "FALSE"


@pytest.mark.django_db
@pytest.mark.parametrize("column", ["is_active", "is_staff"])
@pytest.mark.parametrize(("flag", "expected"), [(True, "TRUE"), (False, "FALSE")])
def test_boolean_columns_read_true_or_false(staff_client, column, flag, expected):
    user = UserFactory(**{column: flag})

    response = _export_user(staff_client, user)

    assert _cell(response, user, column) == expected


@pytest.mark.django_db
def test_created_at_is_iso_8601(staff_client):
    user = UserFactory()

    response = _export_user(staff_client, user)

    assert _cell(response, user, "created_at") == user.created_at.isoformat()


@pytest.mark.django_db
def test_last_login_is_empty_for_a_user_who_never_logged_in(staff_client):
    user = UserFactory(last_login=None)

    response = _export_user(staff_client, user)

    assert _cell(response, user, "last_login") == ""


def test_resource_has_no_credential_or_permission_fields():
    for name in ("password", "is_superuser", "groups", "user_permissions"):
        assert name not in UserResource.fields
