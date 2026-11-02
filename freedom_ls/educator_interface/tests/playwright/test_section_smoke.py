"""Every educator section loads for an organisation admin with no console
errors.

Seven logins in one parametrised test is deliberate: a per-section smoke test
must fail on its own section, which one long flow cannot do.
"""

from __future__ import annotations

from typing import cast

import pytest
from playwright.sync_api import Page, expect

from django.contrib.auth.base_user import AbstractBaseUser
from django.db.models import Model

from freedom_ls.audit_log.writer import record_entry
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.learner_management.factories import (
    CohortFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.role_assignment import assign_role
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation

from .helpers import interface_url, no_console_errors

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]


def seed_sections(user: AbstractBaseUser) -> tuple[Organisation, str]:
    """One organisation with a cohort, a learner, a course registration and an
    audit entry; `user` is its organisation admin. Returns the organisation
    and the cohort's primary key as a string."""
    organisation = cast(Organisation, OrganisationFactory(name="Org A"))
    grantor = LearnerFactory(user__superuser=True).user
    assign_role(grantor, user, "organisation_admin", organisation)
    cohort = CohortFactory(organisation=organisation, name="Evening group")
    learner = LearnerFactory(
        organisation=organisation,
        user__first_name="Ada",
        user__last_name="Lovelace",
    )
    CohortMembershipFactory(cohort=cohort, learner=learner)
    LearnerCourseRegistrationFactory(
        learner=learner, course=CourseFactory(title="Algebra")
    )
    deactivated = LearnerFactory(organisation=organisation, is_active=False)
    record_entry(
        action="learner.deactivated",
        actor=None,
        target=cast(Model, deactivated),
        target_label="Grace Hopper",
        organisation=organisation,
    )
    return organisation, str(cohort.pk)


@pytest.mark.parametrize(
    ("path_string", "heading", "row_text"),
    [
        ("dashboard", "Dashboard", "Evening group"),
        ("learners", "Learners", "Ada Lovelace"),
        ("cohorts", "Cohorts", "Evening group"),
        ("courses", "Courses", "Algebra"),
        ("members", "Members", "{email}"),
        ("audit-log", "Audit log", "Grace Hopper"),
        ("cohorts/{cohort}/__tabs/report", "Cohort report", "Cohort at a glance"),
    ],
)
def test_section_loads_without_console_errors(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
    path_string: str,
    heading: str,
    row_text: str,
) -> None:
    page = educator_logged_in_page
    organisation, cohort_pk = seed_sections(educator_user)

    with no_console_errors(page):
        page.goto(
            interface_url(
                live_server, organisation.slug, path_string.format(cohort=cohort_pk)
            )
        )
        expect(page.get_by_role("heading", name=heading).first).to_be_visible()
        expect(
            page.get_by_text(row_text.format(email=educator_user.email)).first
        ).to_be_visible()
        page.wait_for_load_state("networkidle")
