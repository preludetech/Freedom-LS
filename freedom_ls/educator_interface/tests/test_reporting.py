"""Tests for the cohort members CSV: its rows, ordering, safety and filename."""

from __future__ import annotations

import csv
import io
from collections.abc import Callable
from email.message import Message
from typing import cast

import pytest
import time_machine

from django.contrib.auth.models import AbstractBaseUser
from django.http import HttpResponse
from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.learner_management.factories import (
    CohortFactory,
    CohortMembershipFactory,
    LearnerFactory,
)
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.role_based_permissions.utils import assign_object_role

HEADER = ["Name", "Email", "Role", "Status"]


@pytest.fixture(autouse=True)
def _site_context(mock_site_context):
    """Every test here builds site-aware objects and assigns roles."""


def _csv_url(organisation_slug: str, cohort_pk: object) -> str:
    return reverse(
        "educator_interface:cohort_members_csv",
        kwargs={"organisation_slug": organisation_slug, "cohort_pk": cohort_pk},
    )


def _rows(response: HttpResponse) -> list[list[str]]:
    body = response.content.decode("utf-8-sig")
    return list(csv.reader(io.StringIO(body, newline="")))


def _download(
    logged_in_client: Callable[[AbstractBaseUser], Client], cohort, **user_kwargs
) -> HttpResponse:
    admin = UserFactory(staff=True, **user_kwargs)
    assign_object_role(admin, cohort.organisation, "organisation_admin")
    return cast(
        HttpResponse,
        logged_in_client(admin).get(_csv_url(cohort.organisation.slug, cohort.pk)),
    )


@pytest.mark.django_db
class TestCohortMembersCsv:
    def test_a_formula_looking_name_gets_a_leading_apostrophe(self, logged_in_client):
        cohort = CohortFactory()
        CohortMembershipFactory(
            cohort=cohort,
            learner__user=UserFactory(first_name='=HYPERLINK("x","y")', last_name=""),
        )

        rows = _rows(_download(logged_in_client, cohort))

        assert rows[1][0] == '\'=HYPERLINK("x","y")'

    def test_awkward_names_round_trip_through_a_csv_reader(self, logged_in_client):
        cohort = CohortFactory()
        CohortMembershipFactory(
            cohort=cohort,
            learner__user=UserFactory(first_name="Zoë", last_name="Ñandú"),
        )
        CohortMembershipFactory(
            cohort=cohort,
            learner__user=UserFactory(first_name='Al, "Bo"\nCy', last_name="Zzz"),
        )

        names = {row[0] for row in _rows(_download(logged_in_client, cohort))[1:3]}

        assert names == {"Zoë Ñandú", 'Al, "Bo"\nCy Zzz'}

    def test_the_body_starts_with_a_byte_order_mark_and_the_header(
        self, logged_in_client
    ):
        response = _download(logged_in_client, CohortFactory())

        assert response.content.startswith(b"\xef\xbb\xbf")
        assert _rows(response)[0] == HEADER

    def test_a_removed_learner_is_absent_and_educators_follow_the_learners(
        self, logged_in_client
    ):
        cohort = CohortFactory()
        CohortMembershipFactory(
            cohort=cohort,
            learner__user=UserFactory(first_name="Kept", last_name="Learner"),
        )
        CohortMembershipFactory(
            cohort=cohort,
            learner=LearnerFactory(
                user=UserFactory(first_name="Gone", last_name="Learner"),
                organisation=cohort.organisation,
                is_active=False,
            ),
        )
        educator = UserFactory(first_name="Edna", last_name="Educator")
        assign_object_role(educator, cohort, "cohort_admin")

        rows = _rows(_download(logged_in_client, cohort))

        assert rows[1:] == [
            ["Kept Learner", rows[1][1], "Learner", "Active"],
            ["Edna Educator", educator.email, rows[2][2], ""],
        ]
        assert rows[2][2] != ""

    def test_learner_rows_are_in_surname_order(self, logged_in_client):
        cohort = CohortFactory()
        for first, last in [("Ada", "Zeta"), ("Bo", "Alpha"), ("Cy", "Mu")]:
            CohortMembershipFactory(
                cohort=cohort,
                learner__user=UserFactory(first_name=first, last_name=last),
            )

        rows = _rows(_download(logged_in_client, cohort))

        assert [row[0] for row in rows[1:]] == ["Bo Alpha", "Cy Mu", "Ada Zeta"]

    @time_machine.travel("2026-03-04 10:00:00+00:00", tick=False)
    def test_a_non_ascii_cohort_name_yields_a_parseable_dated_filename(
        self, logged_in_client
    ):
        organisation = OrganisationFactory(name="Škola")
        cohort = CohortFactory(organisation=organisation, name="Třída A")

        response = _download(logged_in_client, cohort)

        message = Message()
        message["Content-Disposition"] = response["Content-Disposition"]
        assert message.get_content_disposition() == "attachment"
        assert message.get_filename() == "škola-třída-a-members-2026-03-04.csv"

    def test_an_organisation_the_user_cannot_access_answers_404(self, logged_in_client):
        cohort = CohortFactory()
        outsider = UserFactory(staff=True)
        assign_object_role(outsider, OrganisationFactory(), "organisation_admin")

        response = logged_in_client(outsider).get(
            _csv_url(cohort.organisation.slug, cohort.pk)
        )

        assert response.status_code == 404

    def test_a_cohort_outside_the_named_organisation_answers_404(
        self, logged_in_client
    ):
        organisation = OrganisationFactory()
        foreign_cohort = CohortFactory()
        admin = UserFactory(staff=True)
        assign_object_role(admin, organisation, "organisation_admin")

        response = logged_in_client(admin).get(
            _csv_url(organisation.slug, foreign_cohort.pk)
        )

        assert response.status_code == 404

    def test_a_cohort_the_cohort_scoped_role_does_not_cover_answers_404(
        self, logged_in_client
    ):
        organisation = OrganisationFactory()
        granted = CohortFactory(organisation=organisation)
        other = CohortFactory(organisation=organisation)
        educator = UserFactory(staff=True)
        assign_object_role(educator, granted, "cohort_admin")
        client = logged_in_client(educator)

        covered = client.get(_csv_url(organisation.slug, granted.pk))
        uncovered = client.get(_csv_url(organisation.slug, other.pk))

        assert (covered.status_code, uncovered.status_code) == (200, 404)

    def test_a_malformed_cohort_id_answers_404(self, logged_in_client):
        organisation = OrganisationFactory()
        admin = UserFactory(staff=True)
        assign_object_role(admin, organisation, "organisation_admin")

        response = logged_in_client(admin).get(_csv_url(organisation.slug, "0" * 36))

        assert response.status_code == 404
