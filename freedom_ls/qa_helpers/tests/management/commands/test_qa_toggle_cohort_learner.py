"""Removing a learner takes only their membership of the named cohort and
deactivates them; restoring puts both back."""

from __future__ import annotations

import pytest

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management import call_command

if "freedom_ls.qa_helpers" not in settings.INSTALLED_APPS:  # pragma: no cover
    pytest.skip("qa_helpers not installed", allow_module_level=True)

from freedom_ls.learner_management.factories import (
    CohortFactory,
    CohortMembershipFactory,
)
from freedom_ls.learner_management.models import CohortMembership

pytestmark = pytest.mark.dev_tooling


@pytest.fixture
def qa_site(mock_site_context) -> Site:
    site: Site = Site.objects.get_current()
    site.name = "DemoDev"
    site.save()
    return site


def _run(action: str, membership: CohortMembership) -> None:
    call_command(
        "qa_toggle_cohort_learner",
        action,
        "--learner-email",
        membership.learner.user.email,
        "--cohort-name",
        membership.cohort.name,
        "--organisation-slug",
        membership.cohort.organisation.slug,
    )


@pytest.mark.django_db
def test_remove_then_restore_touches_only_the_named_cohort(qa_site):
    target = CohortMembershipFactory()
    other_cohort = CohortFactory(organisation=target.cohort.organisation)
    other = CohortMembershipFactory(learner=target.learner, cohort=other_cohort)
    bystander = CohortMembershipFactory(cohort=target.cohort)

    _run("remove", target)

    learner = target.learner
    learner.refresh_from_db()
    assert not learner.is_active
    assert not CohortMembership._base_manager.filter(pk=target.pk).exists()
    assert CohortMembership._base_manager.filter(pk=other.pk).exists()
    assert CohortMembership._base_manager.filter(pk=bystander.pk).exists()

    _run("restore", target)

    learner.refresh_from_db()
    assert learner.is_active
    assert CohortMembership._base_manager.filter(
        learner=learner, cohort=target.cohort
    ).exists()
