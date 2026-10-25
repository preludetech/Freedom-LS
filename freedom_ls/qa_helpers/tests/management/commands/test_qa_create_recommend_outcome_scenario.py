"""The recommend-outcome seed clears an earlier QA run's residue and leaves only
the staff-made registration and recommendation standing."""

from __future__ import annotations

import pytest

from django.contrib.auth.models import Permission
from django.contrib.sites.models import Site
from django.core.management import call_command

from freedom_ls.tests.app_guards import app_not_installed

if (
    app_not_installed("freedom_ls.registration_rules")
    or app_not_installed("freedom_ls.course_recommendations")
    or app_not_installed("freedom_ls.qa_helpers")
):
    pytest.skip(
        "registration_rules, course_recommendations or qa_helpers not installed",
        allow_module_level=True,
    )

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import Course
from freedom_ls.course_recommendations.factories import RecommendedCourseFactory
from freedom_ls.course_recommendations.models import RecommendedCourse
from freedom_ls.hr_attributes.models import LearnerHRAttributes
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
)
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    CohortMembership,
    Learner,
    LearnerCourseRegistration,
)
from freedom_ls.registration_rules.factories import (
    RegistrationRuleFactory,
    RuleRecommendationFactory,
)
from freedom_ls.registration_rules.models import RegistrationRule, RuleRecommendation

pytestmark = [pytest.mark.dev_tooling, pytest.mark.django_db]


def test_rerun_removes_residue_and_keeps_only_the_staff_rows(
    mock_site_context: Site,
) -> None:
    # Arrange
    UserFactory(email="demodev@email.com", superuser=True)
    call_command("qa_create_recommend_outcome_scenario")
    audit = Course._base_manager.get(title="QA Audit Essentials")
    cohort = Cohort._base_manager.get(name="QA Rec Cohort")
    finance = Learner._base_manager.get(user__email="qa_rec_finance@email.com")
    ops = Learner._base_manager.get(user__email="qa_rec_ops@email.com")

    rule = RegistrationRuleFactory(organisation=cohort.organisation, course=audit)
    RuleRecommendationFactory(
        rule=rule, recommendation__user=finance.user, recommendation__course=audit
    )
    RecommendedCourseFactory(user=ops.user, course=audit)
    LearnerCourseRegistrationFactory(learner=finance, course=audit)
    CohortCourseRegistrationFactory(cohort=cohort, course=audit)
    CohortMembershipFactory(cohort=cohort, learner=ops)
    cohort.is_active = False
    cohort.save(update_fields=["is_active"])
    ops.is_active = False
    ops.save(update_fields=["is_active"])
    hr = LearnerHRAttributes._base_manager.get(learner=ops)
    hr.department = LearnerHRAttributes._base_manager.get(learner=finance).department
    hr.save(update_fields=["department"])
    viewer = UserFactory(email="viewer@example.com", staff=True)
    viewer.user_permissions.add(
        Permission.objects.get(codename="view_registrationrule")
    )
    keeper = UserFactory(email="keeper@example.com", staff=True)
    keeper.user_permissions.add(
        *Permission.objects.filter(
            codename__in=["view_registrationrule", "change_registrationrule"]
        )
    )

    # Act
    call_command("qa_create_recommend_outcome_scenario")

    # Assert
    assert not RegistrationRule._base_manager.exists()
    assert not RuleRecommendation._base_manager.exists()
    assert [
        (r.user.email, r.course_id) for r in RecommendedCourse._base_manager.all()
    ] == [("qa_rec_staffrec@email.com", audit.pk)]
    assert [
        (r.learner.user.email, r.is_active, r.self_registered)
        for r in LearnerCourseRegistration._base_manager.filter(course=audit)
    ] == [("qa_rec_registered@email.com", True, False)]
    assert not CohortCourseRegistration._base_manager.exists()
    assert not CohortMembership._base_manager.filter(cohort=cohort).exists()
    cohort.refresh_from_db()
    assert cohort.is_active
    ops.refresh_from_db()
    assert ops.is_active
    assert LearnerHRAttributes._base_manager.filter(
        learner=ops, department__name="Operations"
    ).exists()
    assert not User._base_manager.filter(pk=viewer.pk).exists()
    assert User._base_manager.filter(pk=keeper.pk).exists()
