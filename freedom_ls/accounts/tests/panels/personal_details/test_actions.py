"""Tests for the Personal details actions, through the test client."""

from __future__ import annotations

import re

import pytest

from django.apps import apps
from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.panels.personal_details.actions import (
    ACCOUNT_CHANGED,
    CHANGE_OWN_NAME,
    EditNameAction,
)

pytestmark = pytest.mark.django_db

EDIT_NAME_URL = "/accounts/profile/personal-details/__panels/name/__actions/edit_name"


@pytest.fixture
def signed_in(mock_site_context):
    user = UserFactory(first_name="Ada", last_name="Lovelace")
    client = Client()
    client.force_login(user)
    return client, user


def test_a_valid_save_stores_the_names_and_re_renders_the_form_with_them(signed_in):
    client, user = signed_in

    response = client.post(
        EDIT_NAME_URL,
        {"first_name": "Grace", "last_name": "Hopper"},
        headers={"HX-Request": "true"},
    )

    user.refresh_from_db()
    html = response.content.decode()
    assert response.status_code == 200
    assert (user.first_name, user.last_name) == ("Grace", "Hopper")
    assert 'value="Grace"' in html
    assert 'value="Hopper"' in html
    assert "Name saved" in html
    assert ACCOUNT_CHANGED in response["HX-Trigger"]


def test_blank_names_are_accepted_and_stored_blank(signed_in):
    client, user = signed_in

    response = client.post(EDIT_NAME_URL, {"first_name": "", "last_name": ""})

    user.refresh_from_db()
    assert response.status_code == 200
    assert (user.first_name, user.last_name) == ("", "")


def test_a_first_name_over_200_characters_answers_422_and_stores_nothing(signed_in):
    client, user = signed_in

    response = client.post(
        EDIT_NAME_URL, {"first_name": "A" * 201, "last_name": "Hopper"}
    )

    user.refresh_from_db()
    html = response.content.decode()
    assert response.status_code == 422
    assert (user.first_name, user.last_name) == ("Ada", "Lovelace")
    assert len(re.findall(r'role="alert"', html)) == 1
    assert 'aria-invalid="true"' in html


def test_a_name_save_writes_no_audit_entry(signed_in):
    client, _ = signed_in
    audit_entries = apps.get_model(
        "freedom_ls_audit_log", "AuditLogEntry"
    )._base_manager
    before = audit_entries.count()

    client.post(EDIT_NAME_URL, {"first_name": "Grace", "last_name": "Hopper"})

    assert audit_entries.count() == before


def test_an_anonymous_save_redirects_to_login(mock_site_context):
    response = Client().post(EDIT_NAME_URL, {"first_name": "Grace"})

    assert response.status_code == 302
    assert reverse("account_login") in response.url


def test_the_edit_name_action_needs_the_change_own_name_capability(
    mock_site_context,
):
    action = EditNameAction(UserFactory())

    assert action.get_capability(None) == CHANGE_OWN_NAME
