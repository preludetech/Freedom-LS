"""Tests for can(): the capability check every role assignment answers through."""

from __future__ import annotations

from types import ModuleType
from typing import cast
from unittest.mock import patch

import pytest

from django.contrib.auth.models import AnonymousUser
from django.contrib.sites.models import Site

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.audit_log.models import AuditLogEntry
from freedom_ls.learner_management.capabilities import (
    VIEW_COURSE_QUESTIONS,
    can,
    can_view_course_questions,
    record_question_view,
)
from freedom_ls.learner_management.factories import CohortFactory
from freedom_ls.learner_management.models import Cohort, StaffMember
from freedom_ls.learner_management.queries import (
    VIEW_COURSE_QUESTIONS as QUERIES_VIEW_COURSE_QUESTIONS,
)
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.role_based_permissions.loader import clear_caches
from freedom_ls.role_based_permissions.types import SCOPE_OBJECT, Role, SiteRolesConfig
from freedom_ls.role_based_permissions.utils import assign_object_role, assign_site_role

VIEW_COHORT = "freedom_ls_learner_management.view_cohort"
ADD_COHORT = "freedom_ls_learner_management.add_cohort"
VIEW_ORGANISATION = "freedom_ls_organisations.view_organisation"


@pytest.fixture(autouse=True)
def _clear_role_caches():
    """Every test here reads role config or assigns roles; keep them isolated."""
    clear_caches()
    yield
    clear_caches()


@pytest.mark.django_db
def test_a_superuser_can_do_anything(mock_site_context: Site) -> None:
    organisation = OrganisationFactory()
    user = UserFactory(superuser=True)

    assert can(user, VIEW_ORGANISATION, organisation) is True


@pytest.mark.django_db
def test_an_inactive_user_is_denied_even_with_a_grant(mock_site_context: Site) -> None:
    organisation = OrganisationFactory()
    user = UserFactory(is_active=False)
    assign_object_role(user, organisation, "organisation_admin")

    assert can(user, VIEW_ORGANISATION, organisation) is False


@pytest.mark.django_db
def test_an_anonymous_user_is_denied(mock_site_context: Site) -> None:
    organisation = OrganisationFactory()

    assert can(AnonymousUser(), VIEW_ORGANISATION, organisation) is False


@pytest.mark.django_db
def test_a_site_admin_can_view_and_add_cohorts_in_any_organisation_on_its_site(
    mock_site_context: Site,
) -> None:
    """Closes the gap in role_based_permissions/tests/test_utils.py's
    TestSiteRoleFunctions: a site role was only ever proven to sync onto
    guardian, never checked against an object it doesn't share a content
    type with."""
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    user = UserFactory()
    assign_site_role(user, "site_admin")

    assert can(user, VIEW_COHORT, cohort) is True
    assert can(user, ADD_COHORT, organisation) is True


@pytest.mark.django_db
def test_a_cohort_created_after_the_grant_is_covered_with_nothing_re_synced(
    mock_site_context: Site,
) -> None:
    organisation = OrganisationFactory()
    user = UserFactory()
    assign_object_role(user, organisation, "organisation_admin")

    cohort = CohortFactory(organisation=organisation)

    assert can(user, VIEW_COHORT, cohort) is True


@pytest.mark.django_db
def test_a_changed_role_config_takes_effect_after_clear_caches(
    mock_site_context: Site, settings
) -> None:
    """No guardian re-sync is involved: the grant on the cohort never changes,
    only the role config's own permission set does."""
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    user = UserFactory()
    assign_object_role(user, cohort, "cohort_viewer")
    capability = "freedom_ls_learner_management.a_capability_only_the_new_config_grants"

    assert can(user, capability, cohort) is False

    module_path = "fake_permissions_module_for_test_capabilities"
    fake_module = ModuleType(module_path)
    fake_module.ROLES = SiteRolesConfig(
        {
            "cohort_viewer": Role(
                display_name="Cohort viewer",
                permissions=frozenset({capability}),
                assignment_scope=SCOPE_OBJECT,
            ),
        }
    )
    settings.FREEDOMLS_PERMISSIONS_MODULES = {mock_site_context.name: module_path}

    with patch(
        "freedom_ls.role_based_permissions.loader.import_module",
        return_value=fake_module,
    ):
        clear_caches()
        assert can(user, capability, cohort) is True


@pytest.mark.django_db
def test_a_site_admin_needs_no_staff_member_row(mock_site_context: Site) -> None:
    """A site-level grant never routes through the StaffMember gate --
    _site_grants stays ungated, so a site admin need not belong to every
    organisation on the site to see into all of them."""
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    user = UserFactory()
    assign_site_role(user, "site_admin")

    assert not StaffMember.objects.filter(user=user).exists()
    assert can(user, VIEW_COHORT, cohort) is True


@pytest.mark.django_db
def test_a_site_scope_with_only_an_object_grant_is_denied(
    mock_site_context: Site,
) -> None:
    organisation = OrganisationFactory()
    user = UserFactory()
    assign_object_role(user, organisation, "organisation_admin")

    assert can(user, VIEW_ORGANISATION, mock_site_context) is False


@pytest.mark.django_db
def test_a_question_bank_viewer_may_view_course_questions_in_its_organisation(
    mock_site_context: Site,
) -> None:
    organisation = OrganisationFactory()
    user = UserFactory()
    assign_object_role(user, organisation, "question_bank_viewer")

    assert can_view_course_questions(user, organisation) is True


@pytest.mark.django_db
def test_a_question_bank_viewer_may_not_view_course_questions_in_another_organisation(
    mock_site_context: Site,
) -> None:
    organisation = OrganisationFactory()
    other_organisation = OrganisationFactory()
    user = UserFactory()
    assign_object_role(user, other_organisation, "question_bank_viewer")

    assert can_view_course_questions(user, organisation) is False


@pytest.mark.django_db
def test_an_organisation_admin_may_not_view_course_questions(
    mock_site_context: Site,
) -> None:
    organisation = OrganisationFactory()
    user = UserFactory()
    assign_object_role(user, organisation, "organisation_admin")

    assert can_view_course_questions(user, organisation) is False


@pytest.mark.django_db
def test_a_superuser_may_view_course_questions(mock_site_context: Site) -> None:
    organisation = OrganisationFactory()
    user = UserFactory(superuser=True)

    assert can_view_course_questions(user, organisation) is True


@pytest.mark.django_db
def test_a_holder_with_an_inactive_staff_member_row_may_not_view_course_questions(
    mock_site_context: Site,
) -> None:
    organisation = OrganisationFactory()
    user = UserFactory()
    assign_object_role(user, organisation, "question_bank_viewer")
    StaffMember.objects.filter(user=user, organisation=organisation).update(
        is_active=False
    )

    assert can_view_course_questions(user, organisation) is False


@pytest.mark.django_db
def test_a_cohort_grant_of_the_permission_does_not_pass_the_organisation_check(
    mock_site_context: Site, settings
) -> None:
    """The cohort grant is real (it passes for the cohort itself) but the
    organisation-scoped check never reaches cohort grants."""
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    user = UserFactory()
    assign_object_role(user, cohort, "cohort_viewer")
    module_path = "fake_permissions_module_for_cohort_question_grant"
    fake_module = ModuleType(module_path)
    fake_module.ROLES = SiteRolesConfig(
        {
            "cohort_viewer": Role(
                display_name="Cohort viewer",
                permissions=frozenset({VIEW_COURSE_QUESTIONS}),
                assignment_scope=SCOPE_OBJECT,
            ),
        }
    )
    settings.FREEDOMLS_PERMISSIONS_MODULES = {mock_site_context.name: module_path}

    with patch(
        "freedom_ls.role_based_permissions.loader.import_module",
        return_value=fake_module,
    ):
        clear_caches()
        cohort_check = can(user, VIEW_COURSE_QUESTIONS, cohort)
        organisation_check = can_view_course_questions(user, organisation)

    assert (cohort_check, organisation_check) == (True, False)


def test_the_queries_module_re_exports_the_view_course_questions_constant() -> None:
    assert QUERIES_VIEW_COURSE_QUESTIONS == VIEW_COURSE_QUESTIONS


@pytest.mark.django_db
def test_record_question_view_writes_one_entry_with_what_it_was_given(
    mock_site_context: Site,
) -> None:
    organisation = OrganisationFactory()
    actor = UserFactory()
    subject = cast(Cohort, CohortFactory(organisation=organisation))
    details = {"surface": "cohort_report", "forms": [{"id": "1", "title": "Quiz"}]}

    record_question_view(
        actor=actor,
        target=organisation,
        target_label="Acme",
        organisation=organisation,
        subjects=[subject],
        details=details,
    )

    (entry,) = AuditLogEntry.unscoped.filter(action="question.viewed")
    assert (entry.actor, entry.organisation, entry.target_label, entry.details) == (
        actor,
        organisation,
        "Acme",
        details,
    )
    assert f"freedom_ls_learner_management.cohort:{subject.pk}" in entry.subjects
    assert entry.target_object_id == str(organisation.pk)
