"""The report fixture matrix must be buildable in more than one organisation.

qa_helpers is otherwise untested developer tooling. These fixtures are the
exception because they are destructive: --reset deletes rows, and getting its
scope wrong silently empties a QA dataset somebody is midway through using.
"""

from __future__ import annotations

import pytest

from freedom_ls.accounts.models import User
from freedom_ls.learner_management.factories import (
    CohortFactory,
    CohortMembershipFactory,
)
from freedom_ls.learner_management.models import CohortMembership
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.qa_helpers.management.commands.qa_create_report_cohort import (
    _get_or_create_user,
    organisation_email_prefix,
)
from freedom_ls.qa_helpers.management.commands.qa_create_report_fixtures import (
    COHORT_FIXTURES,
    _reset_fixtures,
)

pytestmark = pytest.mark.fls_internal


def _fixture():
    """One cohort fixture spec, whichever the matrix happens to list first."""
    return COHORT_FIXTURES[0]


def _seed_cohort(site, organisation, fixture, num_learners: int = 2):
    """A fixture cohort in ``organisation``, with its namespaced learners."""
    cohort = CohortFactory(
        name=fixture.cohort_name, site=site, organisation=organisation
    )
    prefix = organisation_email_prefix(fixture.email_prefix, organisation)
    for index in range(num_learners):
        # The command's own lookup, which matches on email alone -- so an
        # un-namespaced prefix really does hand both organisations one set of
        # User rows, rather than the test inventing a second set.
        user = _get_or_create_user(
            site, f"{prefix}-{index + 1:02d}@email.com", "Fixture", "Learner"
        )
        CohortMembershipFactory(
            learner__user=user,
            learner__organisation=organisation,
            cohort=cohort,
            site=site,
        )
    return cohort


@pytest.mark.django_db
def test_a_reset_in_one_organisation_leaves_another_organisations_learners(
    mock_site_context,
):
    """--reset must not reach across organisations.

    Fixture learners are matched by an email prefix. Scoped by site alone, a
    reset in the organisation QA is currently working in would delete the
    learners backing the identically-named fixture cohort in every other
    organisation, cascading their memberships and progress and leaving those
    cohorts standing but empty.
    """
    site = mock_site_context
    fixture = _fixture()
    keep = OrganisationFactory(name="Kept Organisation", slug="kept")
    reset = OrganisationFactory(name="Reset Organisation", slug="reset")
    _seed_cohort(site, keep, fixture)
    _seed_cohort(site, reset, fixture)
    kept_prefix = organisation_email_prefix(fixture.email_prefix, keep)

    _reset_fixtures(site, reset, [fixture])

    kept_learners = User.objects.filter(email__startswith=f"{kept_prefix}-")
    assert kept_learners.count() == 2
    assert CohortMembership.objects.filter(learner__organisation=keep).count() == 2


@pytest.mark.django_db
def test_a_reset_deletes_its_own_organisations_learners(mock_site_context):
    """The other half of the scoping claim: the target really is cleared.

    Without this, scoping the delete to nothing at all would pass the test
    above for the wrong reason.
    """
    site = mock_site_context
    fixture = _fixture()
    organisation = OrganisationFactory(name="Reset Organisation", slug="reset")
    _seed_cohort(site, organisation, fixture)
    prefix = organisation_email_prefix(fixture.email_prefix, organisation)

    _reset_fixtures(site, organisation, [fixture])

    assert not User.objects.filter(email__startswith=f"{prefix}-").exists()


@pytest.mark.django_db
def test_learner_emails_are_namespaced_per_organisation(mock_site_context):
    """Two organisations must not share one set of learner rows.

    _get_or_create_user matches on email alone, so an un-namespaced prefix
    hands both organisations' cohorts the same User rows -- which is what makes
    a cross-organisation delete destructive in the first place, and what stops
    either organisation being reset independently of the other.
    """
    first = OrganisationFactory(name="First", slug="first")
    second = OrganisationFactory(name="Second", slug="second")

    assert organisation_email_prefix("qa-report-std", first) != (
        organisation_email_prefix("qa-report-std", second)
    )


@pytest.mark.django_db
def test_a_long_organisation_slug_is_truncated_and_disambiguated(mock_site_context):
    """Two long slugs sharing a leading run must still get distinct prefixes.

    An email local part is capped at 64 characters, so the organisation token
    cannot simply be the slug; truncating it alone would collide.
    """
    shared = "national-federation-of-technical-institutes"
    first = OrganisationFactory(name="First", slug=f"{shared}-north")
    second = OrganisationFactory(name="Second", slug=f"{shared}-south")

    first_prefix = organisation_email_prefix("qa-report-std", first)
    second_prefix = organisation_email_prefix("qa-report-std", second)

    assert first_prefix != second_prefix
    assert len(f"{first_prefix}-01") <= 64


@pytest.mark.django_db
def test_a_non_ascii_organisation_slug_yields_an_ascii_email_prefix(mock_site_context):
    """A non-Latin organisation name must still produce a usable email."""
    organisation = OrganisationFactory(
        name="Восточно-Европейская Академия", slug="восточно-европейская-академия"
    )

    prefix = organisation_email_prefix("qa-report-std", organisation)

    assert prefix.isascii()
    assert prefix.startswith("qa-report-std-")


@pytest.mark.django_db
def test_one_organisations_prefix_is_never_a_prefix_of_anothers(mock_site_context):
    """`startswith` matching needs the boundary to be unambiguous.

    _reset_fixtures deletes on email__startswith, so an organisation whose
    token is a leading substring of another's would sweep up the other's
    learners despite the namespacing.
    """
    north = OrganisationFactory(name="North", slug="north")
    northside = OrganisationFactory(name="Northside", slug="northside")

    north_prefix = f"{organisation_email_prefix('qa-report-std', north)}-"
    northside_email = f"{organisation_email_prefix('qa-report-std', northside)}-01"

    assert not northside_email.startswith(north_prefix)
