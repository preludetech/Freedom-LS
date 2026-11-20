"""A user changing their own account writes no audit entry: the audit log
records what staff do to an organisation's records."""

from __future__ import annotations

import pytest

from django.contrib.sites.models import Site
from django.test import Client

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.audit_log.models import AuditLogEntry

EDIT_NAME_URL = "/accounts/profile/personal-details/__panels/name/__actions/edit_name"


@pytest.mark.django_db
def test_a_name_save_writes_no_audit_entry(mock_site_context: Site) -> None:
    client = Client()
    client.force_login(UserFactory(first_name="Ada", last_name="Lovelace"))

    response = client.post(
        EDIT_NAME_URL,
        {"first_name": "Grace", "last_name": "Hopper"},
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 200
    assert AuditLogEntry._base_manager.count() == 0
