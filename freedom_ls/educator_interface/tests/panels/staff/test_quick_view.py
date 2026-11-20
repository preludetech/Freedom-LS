"""Tests for the staff quick view."""

from __future__ import annotations

import lxml.html
import pytest

from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.educator_interface.tests.helpers import (
    _hold,
    _staff_document,
    _staff_member_row,
)
from freedom_ls.organisations.factories import OrganisationFactory


def _staff_quick_view_text(client: Client, organisation, email: str) -> str:
    user = User.objects.get(email=email)
    response = client.get(
        reverse(
            "educator_interface:interface",
            kwargs={
                "organisation_slug": organisation.slug,
                "path_string": f"staff/{user.pk}/__quick-view",
            },
        ),
        HTTP_HX_REQUEST="true",
    )
    assert response.status_code == 200
    body = lxml.html.fromstring(response.content.decode())
    return " ".join(body.text_content().split())


@pytest.mark.django_db
def test_a_role_names_who_added_it(role_holder_client):
    organisation = OrganisationFactory()
    grantor = UserFactory(superuser=True, first_name="Grace", last_name="Hopper")
    _hold(
        UserFactory(email="added@example.com"),
        "organisation_admin",
        organisation,
        grantor,
    )
    client = role_holder_client(organisation, "organisation_admin")

    row = _staff_member_row(_staff_document(client, organisation), "added@example.com")
    quick_view = _staff_quick_view_text(client, organisation, "added@example.com")

    assert "by Grace Hopper" not in row.text_content()
    assert "by Grace Hopper" in quick_view


@pytest.mark.django_db
def test_a_role_with_no_recorded_grantor_reads_added_without_a_by_clause(
    role_holder_client,
):
    organisation = OrganisationFactory()
    grantor = UserFactory(superuser=True)
    _hold(
        UserFactory(email="orphan@example.com"),
        "organisation_admin",
        organisation,
        grantor,
    )
    grantor.delete()
    client = role_holder_client(organisation, "organisation_admin")

    text = _staff_quick_view_text(client, organisation, "orphan@example.com")

    assert "Added" in text
    assert " by " not in text
    assert "Not recorded" not in text
