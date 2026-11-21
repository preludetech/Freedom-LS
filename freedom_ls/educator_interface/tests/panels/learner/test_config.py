"""The learners section config: educator_interface/panels/learner/config.py.

A learner from another organisation answers the unavailable dialog or the page 404.
"""

from __future__ import annotations

import uuid

import pytest

from django.template.loader import render_to_string
from django.test import Client

from freedom_ls.educator_interface.tests.helpers import (
    _get_table_fragment,
    _interface_url,
)
from freedom_ls.learner_management.factories import LearnerFactory
from freedom_ls.organisations.factories import OrganisationFactory


@pytest.mark.django_db
def test_a_table_fragment_of_a_learner_from_another_organisation_answers_the_dialog(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    elsewhere = LearnerFactory(organisation=OrganisationFactory())

    response = _get_table_fragment(
        staff_client, _interface_url(organisation.slug, f"learners/{elsewhere.pk}")
    )

    assert response.status_code == 404
    assert "This is no longer available" in response.content.decode()


@pytest.mark.django_db
def test_a_table_fragment_of_an_unknown_learner_answers_the_dialog(
    staff_client: Client,
):
    organisation = OrganisationFactory()

    response = _get_table_fragment(
        staff_client, _interface_url(organisation.slug, f"learners/{uuid.uuid4()}")
    )

    assert response.status_code == 404
    assert "This is no longer available" in response.content.decode()


@pytest.mark.django_db
def test_the_out_of_scope_dialog_is_byte_equal_to_the_unavailable_template(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    elsewhere = LearnerFactory(organisation=OrganisationFactory())

    response = _get_table_fragment(
        staff_client, _interface_url(organisation.slug, f"learners/{elsewhere.pk}")
    )

    assert response.content.decode() == render_to_string(
        "panel_framework/partials/action_unavailable.html"
    )


@pytest.mark.django_db
def test_a_plain_request_for_an_unknown_learner_gets_the_page_404(
    staff_client: Client,
):
    organisation = OrganisationFactory()

    response = staff_client.get(
        _interface_url(organisation.slug, f"learners/{uuid.uuid4()}")
    )

    assert response.status_code == 404
    assert "data-htmx-swap-error" not in response.content.decode()
