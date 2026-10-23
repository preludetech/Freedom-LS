"""The registration rules seed clears an earlier QA run's residue and leaves
only the staff-made registration standing."""

from __future__ import annotations

import pytest

from django.contrib.auth.models import Permission
from django.contrib.sites.models import Site
from django.core.management import call_command

from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.registration_rules") or app_not_installed(
    "freedom_ls.qa_helpers"
):
    pytest.skip(
        "registration_rules or qa_helpers not installed", allow_module_level=True
    )

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.learner_management.models import LearnerCourseRegistration
from freedom_ls.registration_rules.factories import RuleRegistrationFactory
from freedom_ls.registration_rules.models import RegistrationRule, RuleRegistration

pytestmark = [pytest.mark.dev_tooling, pytest.mark.django_db]


def test_rerun_removes_residue_and_keeps_only_the_staff_registration(
    mock_site_context: Site,
) -> None:
    # Arrange
    UserFactory(email="demodev@email.com", superuser=True)
    call_command("qa_create_registration_rules_scenario")
    staff_registration = LearnerCourseRegistration._base_manager.get(
        learner__user__email="qa_rule_staff@email.com"
    )
    rule_made = RuleRegistrationFactory(registration__course=staff_registration.course)
    UserFactory(email="qa_rule_joiner@email.com")
    viewer = UserFactory(email="qa_rule_viewer@email.com", staff=True)
    viewer.user_permissions.add(
        Permission.objects.get(codename="view_registrationrule")
    )
    keeper = UserFactory(email="qa_rule_editor@email.com", staff=True)
    keeper.user_permissions.add(
        *Permission.objects.filter(
            codename__in=["view_registrationrule", "change_registrationrule"]
        )
    )

    # Act
    call_command("qa_create_registration_rules_scenario")

    # Assert
    assert not RegistrationRule._base_manager.exists()
    assert not RuleRegistration._base_manager.exists()
    assert not LearnerCourseRegistration._base_manager.filter(
        pk=rule_made.registration_id
    ).exists()
    assert not User._base_manager.filter(
        email__in=["qa_rule_joiner@email.com", "qa_rule_viewer@email.com"]
    ).exists()
    assert User._base_manager.filter(pk=keeper.pk).exists()
    remaining = LearnerCourseRegistration._base_manager.filter(
        course=staff_registration.course
    )
    assert [
        (r.learner.user.email, r.is_active, r.self_registered) for r in remaining
    ] == [("qa_rule_staff@email.com", True, False)]
