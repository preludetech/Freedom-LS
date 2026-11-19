"""The admonition QA seed deletes only rows in its own fixtures: other staff on the
solo organisation and the move learner's memberships outside the source cohort."""

from __future__ import annotations

import pytest

from django.contrib.sites.models import Site

from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.qa_helpers"):
    pytest.skip("qa_helpers not installed", allow_module_level=True)

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.learner_management.factories import (
    CohortFactory,
    CohortMembershipFactory,
    LearnerFactory,
    StaffMemberFactory,
)
from freedom_ls.learner_management.models import CohortMembership, StaffMember
from freedom_ls.learner_management.queries import staff_of
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.qa_helpers.management.commands.qa_create_admonition_scenarios import (
    MOVE_LEARNER_EMAIL,
    MOVE_SOURCE,
    SOLO_ORG_SLUG,
    _ensure_move_cohorts,
    _ensure_solo_org,
)

pytestmark = [pytest.mark.django_db, pytest.mark.dev_tooling]


def test_solo_org_drops_other_staff_and_keeps_staff_elsewhere(mock_site_context):
    site: Site = Site.objects.get_current()
    viewer = UserFactory(site=site, is_superuser=True)
    solo = OrganisationFactory(site=site, name="QA Solo Org", slug=SOLO_ORG_SLUG)
    other = UserFactory(site=site)
    StaffMemberFactory(site=site, user=other, organisation=solo)
    elsewhere = StaffMemberFactory(site=site, user=other)

    _ensure_solo_org(site, viewer)
    _ensure_solo_org(site, viewer)

    assert list(staff_of(solo)) == [viewer]
    assert StaffMember._base_manager.filter(pk=elsewhere.pk).exists()


def test_move_learner_is_left_in_the_source_cohort_only(mock_site_context):
    site: Site = Site.objects.get_current()
    organisation = OrganisationFactory(site=site)
    learner = LearnerFactory(
        site=site,
        organisation=organisation,
        user=UserFactory(site=site, email=MOVE_LEARNER_EMAIL),
    )
    CohortMembershipFactory(
        site=site, learner=learner, cohort=CohortFactory(organisation=organisation)
    )
    bystander = CohortMembershipFactory(
        site=site, cohort=CohortFactory(organisation=organisation)
    )

    _ensure_move_cohorts(site, organisation)
    _ensure_move_cohorts(site, organisation)

    assert list(
        CohortMembership._base_manager.filter(learner=learner).values_list(
            "cohort__name", flat=True
        )
    ) == [MOVE_SOURCE]
    assert CohortMembership._base_manager.filter(pk=bystander.pk).exists()
