from __future__ import annotations

from typing import cast

import pytest

from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.audit_log.models import AuditLogEntry
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import CourseAudience
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.learner_actions import (
    AddLearnerResult,
    AddOutcome,
    CohortOutcome,
    LearnerEntry,
    add_learners,
    add_to_cohort,
    deactivate_learner,
    deactivate_registration,
    move_between_cohorts,
    reactivate_learner,
    register_for_course,
    remove_from_cohort,
)
from freedom_ls.learner_management.models import (
    Cohort,
    CohortMembership,
    Learner,
    LearnerCourseRegistration,
)
from freedom_ls.learner_management.queries import CourseNotOpenError
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.tests.audit_assertions import assert_entry
from freedom_ls.tests.factories import SiteFactory
from freedom_ls.webhooks.models import WebhookEvent


@pytest.mark.django_db
class TestLearnerStateAudit:
    def test_deactivating_writes_one_entry_with_actor_organisation_and_label(
        self, mock_site_context
    ):
        learner = LearnerFactory(is_active=True)
        actor = UserFactory()

        deactivate_learner(learner, actor=actor)

        assert_entry(
            action="learner.deactivated",
            actor=actor,
            target=learner,
            target_label=learner.user.display_name,
            organisation=learner.organisation,
        )

    def test_deactivating_an_inactive_learner_writes_nothing(self, mock_site_context):
        learner = LearnerFactory(is_active=False)

        deactivate_learner(learner, actor=UserFactory())

        assert AuditLogEntry.unscoped.count() == 0

    def test_reactivating_writes_a_learner_reactivated_entry(self, mock_site_context):
        learner = LearnerFactory(is_active=False)
        actor = UserFactory()

        reactivate_learner(learner, actor=actor)

        assert_entry(
            action="learner.reactivated",
            actor=actor,
            target=learner,
            target_label=learner.user.display_name,
            organisation=learner.organisation,
        )

    def test_the_reason_is_stored_on_the_entry(self, mock_site_context):
        learner = LearnerFactory(is_active=True)

        deactivate_learner(learner, actor=UserFactory(), reason=" Left ")

        assert AuditLogEntry.unscoped.get().reason == "Left"

    def test_a_rollback_after_the_call_leaves_no_entry(self, mock_site_context):
        learner = LearnerFactory(is_active=True)

        def deactivate_then_fail() -> None:
            with transaction.atomic():
                deactivate_learner(learner, actor=UserFactory())
                raise RuntimeError("rolled back")

        with pytest.raises(RuntimeError, match="rolled back"):
            deactivate_then_fail()

        assert AuditLogEntry.unscoped.count() == 0

    def test_no_actor_writes_a_system_entry(self, mock_site_context):
        learner = LearnerFactory(is_active=True)

        deactivate_learner(learner)

        entry = AuditLogEntry.unscoped.get()
        assert (entry.actor, entry.actor_label) == (None, "")


def _added_learner(results: list[AddLearnerResult]) -> Learner:
    learner = results[0].learner
    assert learner is not None
    return learner


def _cohort(organisation: Organisation) -> Cohort:
    return cast(Cohort, CohortFactory(organisation=organisation))


@pytest.mark.django_db
class TestMembershipAudit:
    def test_adding_to_a_cohort_writes_an_entry_naming_the_cohort(
        self, mock_site_context
    ):
        learner = LearnerFactory()
        cohort = _cohort(learner.organisation)
        actor = UserFactory()

        add_to_cohort(learner, cohort, actor=actor, reason="Term start")

        assert_entry(
            action="cohort_membership.added",
            actor=actor,
            target=learner,
            target_label=learner.user.display_name,
            organisation=learner.organisation,
            subjects=[cohort],
            details={"cohort": cohort.name},
            reason="Term start",
        )

    def test_adding_to_a_cohort_the_learner_is_in_writes_nothing(
        self, mock_site_context
    ):
        learner = LearnerFactory()
        cohort = _cohort(learner.organisation)
        CohortMembershipFactory(learner=learner, cohort=cohort)

        add_to_cohort(learner, cohort, actor=UserFactory())

        assert AuditLogEntry.unscoped.count() == 0

    def test_removing_from_a_cohort_writes_an_entry_naming_the_cohort(
        self, mock_site_context
    ):
        learner = LearnerFactory()
        cohort = _cohort(learner.organisation)
        CohortMembershipFactory(learner=learner, cohort=cohort)
        actor = UserFactory()

        remove_from_cohort(learner, cohort, actor=actor)

        assert_entry(
            action="cohort_membership.removed",
            actor=actor,
            target=learner,
            target_label=learner.user.display_name,
            organisation=learner.organisation,
            subjects=[cohort],
            details={"cohort": cohort.name},
        )

    def test_removing_from_a_cohort_the_learner_is_not_in_writes_nothing(
        self, mock_site_context
    ):
        learner = LearnerFactory()
        cohort = _cohort(learner.organisation)

        remove_from_cohort(learner, cohort, actor=UserFactory())

        assert AuditLogEntry.unscoped.count() == 0

    def test_a_move_writes_one_entry_naming_both_cohorts(self, mock_site_context):
        learner = LearnerFactory()
        source = _cohort(learner.organisation)
        destination = _cohort(learner.organisation)
        CohortMembershipFactory(learner=learner, cohort=source)
        actor = UserFactory()

        move_id = move_between_cohorts(learner, source, destination, actor=actor)

        assert_entry(
            action="cohort_membership.moved",
            actor=actor,
            target=learner,
            target_label=learner.user.display_name,
            organisation=learner.organisation,
            subjects=[source, destination],
            details={
                "source": source.name,
                "destination": destination.name,
                "move_id": move_id,
            },
        )

    def test_a_refused_move_writes_nothing(self, mock_site_context):
        learner = LearnerFactory()
        source = _cohort(learner.organisation)
        destination = _cohort(learner.organisation)

        with pytest.raises(ValueError, match="not a member"):
            move_between_cohorts(learner, source, destination, actor=UserFactory())

        assert AuditLogEntry.unscoped.count() == 0

    def test_adding_a_new_address_writes_learner_added_with_the_outcome(
        self, mock_site_context
    ):
        organisation = OrganisationFactory()
        actor = UserFactory()

        learner = _added_learner(
            add_learners(organisation, [LearnerEntry("new@example.com")], actor=actor)
        )

        assert_entry(
            action="learner.added",
            actor=actor,
            target=learner,
            target_label=learner.user.display_name,
            organisation=organisation,
            details={"outcome": "created"},
        )

    def test_adding_to_a_cohort_names_it_on_the_learner_added_entry(
        self, mock_site_context
    ):
        organisation = OrganisationFactory()
        cohort = _cohort(organisation)

        learner = _added_learner(
            add_learners(
                organisation,
                [LearnerEntry("new@example.com")],
                cohort,
                actor=UserFactory(),
            )
        )

        assert_entry(
            action="learner.added",
            actor=AuditLogEntry.unscoped.get().actor,
            target=learner,
            target_label=learner.user.display_name,
            organisation=organisation,
            subjects=[cohort],
            details={"outcome": "created", "cohort": cohort.name},
        )

    def test_reactivating_a_learner_into_a_cohort_writes_exactly_one_entry(
        self, mock_site_context
    ):
        organisation = OrganisationFactory()
        learner = LearnerFactory(organisation=organisation, is_active=False)
        cohort = _cohort(organisation)

        add_learners(
            organisation,
            [LearnerEntry(learner.user.email)],
            cohort,
            actor=UserFactory(),
        )

        entry = AuditLogEntry.unscoped.get()
        assert (entry.action, entry.details) == (
            "learner.reactivated",
            {"cohort": cohort.name},
        )

    def test_an_already_active_learner_newly_in_the_cohort_writes_a_membership_entry(
        self, mock_site_context
    ):
        organisation = OrganisationFactory()
        learner = LearnerFactory(organisation=organisation)
        cohort = _cohort(organisation)

        add_learners(
            organisation,
            [LearnerEntry(learner.user.email)],
            cohort,
            actor=UserFactory(),
        )

        entry = AuditLogEntry.unscoped.get()
        assert (entry.action, entry.details) == (
            "cohort_membership.added",
            {"cohort": cohort.name},
        )

    def test_an_already_active_learner_already_in_the_cohort_writes_nothing(
        self, mock_site_context
    ):
        organisation = OrganisationFactory()
        learner = LearnerFactory(organisation=organisation)
        cohort = _cohort(organisation)
        CohortMembershipFactory(learner=learner, cohort=cohort)

        add_learners(organisation, [LearnerEntry(learner.user.email)], cohort)

        assert AuditLogEntry.unscoped.count() == 0

    def test_a_rollback_after_each_function_leaves_no_entry(self, mock_site_context):
        organisation = OrganisationFactory()
        member = LearnerFactory(organisation=organisation)
        outsider = LearnerFactory(organisation=organisation)
        source = _cohort(organisation)
        destination = _cohort(organisation)
        CohortMembershipFactory(learner=member, cohort=source)

        def run_then_fail() -> None:
            with transaction.atomic():
                add_to_cohort(outsider, source, actor=UserFactory())
                remove_from_cohort(member, source, actor=UserFactory())
                move_between_cohorts(outsider, source, destination, actor=UserFactory())
                add_learners(organisation, [LearnerEntry("new@example.com")])
                raise RuntimeError("rolled back")

        with pytest.raises(RuntimeError, match="rolled back"):
            run_then_fail()

        assert AuditLogEntry.unscoped.count() == 0


@pytest.mark.django_db
class TestRegistrationAudit:
    def test_registering_writes_registration_added_naming_the_course(
        self, mock_site_context
    ):
        learner = LearnerFactory()
        course = CourseFactory(title="Algebra")
        actor = UserFactory()

        register_for_course(learner, course, actor=actor)

        assert_entry(
            action="registration.added",
            actor=actor,
            target=learner,
            target_label=learner.user.display_name,
            organisation=learner.organisation,
            details={"course": "Algebra"},
        )

    def test_reactivating_a_registration_writes_registration_reregistered(
        self, mock_site_context
    ):
        registration = LearnerCourseRegistrationFactory(is_active=False)
        actor = UserFactory()

        register_for_course(registration.learner, registration.course, actor=actor)

        assert_entry(
            action="registration.reactivated",
            actor=actor,
            target=registration.learner,
            target_label=registration.learner.user.display_name,
            organisation=registration.learner.organisation,
            details={"course": registration.course.title},
        )

    def test_registering_when_already_registered_writes_nothing(
        self, mock_site_context
    ):
        registration = LearnerCourseRegistrationFactory(is_active=True)

        register_for_course(
            registration.learner, registration.course, actor=UserFactory()
        )

        assert AuditLogEntry.unscoped.count() == 0

    def test_unregistering_writes_registration_unregistered(self, mock_site_context):
        registration = LearnerCourseRegistrationFactory(is_active=True)
        actor = UserFactory()

        deactivate_registration(registration.learner, registration.course, actor=actor)

        assert_entry(
            action="registration.deactivated",
            actor=actor,
            target=registration.learner,
            target_label=registration.learner.user.display_name,
            organisation=registration.learner.organisation,
            details={"course": registration.course.title},
        )

    def test_unregistering_without_an_active_registration_writes_nothing(
        self, mock_site_context
    ):
        registration = LearnerCourseRegistrationFactory(is_active=False)

        deactivate_registration(
            registration.learner, registration.course, actor=UserFactory()
        )

        assert AuditLogEntry.unscoped.count() == 0

    def test_a_rollback_after_each_function_leaves_no_entry(self, mock_site_context):
        learner = LearnerFactory()
        registered = LearnerCourseRegistrationFactory(learner=learner, is_active=True)

        def run_then_fail() -> None:
            with transaction.atomic():
                register_for_course(learner, CourseFactory(), actor=UserFactory())
                deactivate_registration(learner, registered.course, actor=UserFactory())
                raise RuntimeError("rolled back")

        with pytest.raises(RuntimeError, match="rolled back"):
            run_then_fail()

        assert AuditLogEntry.unscoped.count() == 0


@pytest.mark.django_db
class TestDeactivateLearner:
    def test_sets_the_learner_inactive_and_returns_true(self, mock_site_context):
        learner = LearnerFactory(is_active=True)

        changed = deactivate_learner(learner)

        learner.refresh_from_db()
        assert (changed, learner.is_active) == (True, False)

    def test_records_one_learner_deactivated_event_with_the_payload(
        self, mock_site_context, django_capture_on_commit_callbacks
    ):
        learner = LearnerFactory(is_active=True)

        with django_capture_on_commit_callbacks(execute=True):
            deactivate_learner(learner)

        event = WebhookEvent._base_manager.get()
        assert event.event_type == "learner.deactivated"
        assert event.site_id == learner.site_id
        assert event.payload == {
            "user_id": learner.user.pk,
            "user_email": learner.user.email,
            "organisation_id": str(learner.organisation_id),
            "learner_id": str(learner.pk),
        }

    def test_a_second_call_returns_false(self, mock_site_context):
        learner = LearnerFactory(is_active=False)

        assert deactivate_learner(learner) is False

    def test_a_second_call_records_nothing(
        self, mock_site_context, django_capture_on_commit_callbacks
    ):
        learner = LearnerFactory(is_active=False)

        with django_capture_on_commit_callbacks(execute=True):
            deactivate_learner(learner)

        assert WebhookEvent._base_manager.count() == 0

    def test_leaves_registrations_and_memberships_in_place(self, mock_site_context):
        learner = LearnerFactory(is_active=True)
        CohortMembershipFactory(learner=learner)
        LearnerCourseRegistrationFactory(learner=learner)

        deactivate_learner(learner)

        assert (
            CohortMembership.objects.filter(learner=learner).count(),
            LearnerCourseRegistration.objects.filter(
                learner=learner, is_active=True
            ).count(),
        ) == (1, 1)

    def test_leaves_cohort_registrations_active(self, mock_site_context):
        learner = LearnerFactory(is_active=True)
        membership = CohortMembershipFactory(learner=learner)
        registration = CohortCourseRegistrationFactory(cohort=membership.cohort)

        deactivate_learner(learner)

        registration.refresh_from_db()
        assert registration.is_active is True


@pytest.mark.django_db
class TestReactivateLearner:
    def test_sets_the_learner_active_and_returns_true(self, mock_site_context):
        learner = LearnerFactory(is_active=False)

        changed = reactivate_learner(learner)

        assert (changed, Learner.objects.get(pk=learner.pk).is_active) == (True, True)

    def test_records_one_learner_reactivated_event(
        self, mock_site_context, django_capture_on_commit_callbacks
    ):
        learner = LearnerFactory(is_active=False)

        with django_capture_on_commit_callbacks(execute=True):
            reactivate_learner(learner)

        event = WebhookEvent._base_manager.get()
        assert (event.event_type, event.payload["learner_id"]) == (
            "learner.reactivated",
            str(learner.pk),
        )

    def test_a_second_call_returns_false_and_records_nothing(
        self, mock_site_context, django_capture_on_commit_callbacks
    ):
        learner = LearnerFactory(is_active=True)

        with django_capture_on_commit_callbacks(execute=True):
            changed = reactivate_learner(learner)

        assert (changed, WebhookEvent._base_manager.count()) == (False, 0)


def _member(is_active_cohort: bool = True):
    cohort = CohortFactory(is_active=is_active_cohort)
    learner = LearnerFactory(organisation=cohort.organisation)
    CohortMembershipFactory(cohort=cohort, learner=learner)
    return learner, cohort


@pytest.mark.django_db
class TestRemoveFromCohort:
    def test_deletes_the_membership(self, mock_site_context):
        learner, cohort = _member()

        removed = remove_from_cohort(learner, cohort)

        assert (
            removed,
            CohortMembership.objects.filter(learner=learner, cohort=cohort).exists(),
        ) == (True, False)

    def test_records_one_member_removed_event_without_a_move_id(
        self, mock_site_context, django_capture_on_commit_callbacks
    ):
        learner, cohort = _member()

        with django_capture_on_commit_callbacks(execute=True):
            remove_from_cohort(learner, cohort)

        event = WebhookEvent._base_manager.get()
        assert event.event_type == "cohort_membership.removed"
        assert event.payload == {
            "user_id": learner.user.pk,
            "user_email": learner.user.email,
            "organisation_id": str(learner.organisation_id),
            "learner_id": str(learner.pk),
            "cohort_id": str(cohort.pk),
            "cohort_name": cohort.name,
            "move_id": None,
        }

    def test_a_repeat_returns_false(self, mock_site_context):
        learner, cohort = _member()
        remove_from_cohort(learner, cohort)

        assert remove_from_cohort(learner, cohort) is False

    def test_a_repeat_records_nothing(
        self, mock_site_context, django_capture_on_commit_callbacks
    ):
        learner, cohort = _member()
        remove_from_cohort(learner, cohort)

        with django_capture_on_commit_callbacks(execute=True):
            remove_from_cohort(learner, cohort)

        assert WebhookEvent._base_manager.count() == 0

    def test_refuses_another_organisations_cohort_and_changes_nothing(
        self, mock_site_context
    ):
        learner, _ = _member()
        elsewhere = CohortFactory(organisation=OrganisationFactory())

        with pytest.raises(ValueError, match="another organisation"):
            remove_from_cohort(learner, elsewhere)

        assert CohortMembership.objects.filter(learner=learner).count() == 1

    def test_refuses_an_inactive_cohort_and_changes_nothing(self, mock_site_context):
        learner, cohort = _member(is_active_cohort=False)

        with pytest.raises(ValueError, match="inactive"):
            remove_from_cohort(learner, cohort)

        assert CohortMembership.objects.filter(learner=learner).count() == 1


@pytest.mark.django_db
class TestAddToCohort:
    def test_creates_the_membership_once(self, mock_site_context):
        cohort = CohortFactory()
        learner = LearnerFactory(organisation=cohort.organisation)

        added = add_to_cohort(learner, cohort)

        assert (
            added,
            CohortMembership.objects.filter(learner=learner, cohort=cohort).count(),
        ) == (True, 1)

    def test_records_one_member_added_event_without_a_move_id(
        self, mock_site_context, django_capture_on_commit_callbacks
    ):
        cohort = CohortFactory()
        learner = LearnerFactory(organisation=cohort.organisation)

        with django_capture_on_commit_callbacks(execute=True):
            add_to_cohort(learner, cohort)

        event = WebhookEvent._base_manager.get()
        assert event.event_type == "cohort_membership.added"
        assert event.payload == {
            "user_id": learner.user.pk,
            "user_email": learner.user.email,
            "organisation_id": str(learner.organisation_id),
            "learner_id": str(learner.pk),
            "cohort_id": str(cohort.pk),
            "cohort_name": cohort.name,
            "move_id": None,
        }

    def test_a_repeat_returns_false(self, mock_site_context):
        learner, cohort = _member()

        assert add_to_cohort(learner, cohort) is False

    def test_a_repeat_records_nothing(
        self, mock_site_context, django_capture_on_commit_callbacks
    ):
        learner, cohort = _member()

        with django_capture_on_commit_callbacks(execute=True):
            add_to_cohort(learner, cohort)

        assert WebhookEvent._base_manager.count() == 0

    def test_refuses_another_organisations_cohort_and_changes_nothing(
        self, mock_site_context
    ):
        learner = LearnerFactory()
        elsewhere = CohortFactory(organisation=OrganisationFactory())

        with pytest.raises(ValueError, match="another organisation"):
            add_to_cohort(learner, elsewhere)

        assert CohortMembership.objects.filter(learner=learner).count() == 0

    def test_refuses_an_inactive_cohort_and_changes_nothing(self, mock_site_context):
        cohort = CohortFactory(is_active=False)
        learner = LearnerFactory(organisation=cohort.organisation)

        with pytest.raises(ValueError, match="inactive"):
            add_to_cohort(learner, cohort)

        assert CohortMembership.objects.filter(learner=learner).count() == 0


def _outcome(organisation, email, cohort=None):
    return add_learners(organisation, [LearnerEntry(email)], cohort)[0]


@pytest.mark.django_db
class TestAddLearners:
    def test_a_new_address_is_created_and_sent_the_setup_email(
        self, mock_site_context, django_capture_on_commit_callbacks, mailoutbox
    ):
        organisation = OrganisationFactory()

        with django_capture_on_commit_callbacks(execute=True):
            result = _outcome(organisation, "new@example.com")

        assert result.outcome == AddOutcome.CREATED
        assert [m.to for m in mailoutbox] == [["new@example.com"]]

    def test_an_existing_user_joins_the_organisation(self, mock_site_context):
        organisation = OrganisationFactory()
        user = UserFactory(email="known@example.com")

        result = _outcome(organisation, "known@example.com")

        assert result.outcome == AddOutcome.JOINED
        assert result.learner.user == user

    def test_a_removed_learner_is_reactivated(self, mock_site_context):
        organisation = OrganisationFactory()
        learner = LearnerFactory(organisation=organisation, is_active=False)

        result = _outcome(organisation, learner.user.email)

        learner.refresh_from_db()
        assert (result.outcome, learner.is_active) == (AddOutcome.REACTIVATED, True)

    def test_an_active_learner_is_reported_as_already_a_learner(
        self, mock_site_context
    ):
        organisation = OrganisationFactory()
        learner = LearnerFactory(organisation=organisation)

        result = _outcome(organisation, learner.user.email)

        assert result.outcome == AddOutcome.ALREADY_LEARNER

    def test_an_invalid_address_is_reported_and_creates_no_user(
        self, mock_site_context
    ):
        organisation = OrganisationFactory()
        before = User._base_manager.count()

        result = _outcome(organisation, "not-an-email")

        assert (result.outcome, User._base_manager.count()) == (
            AddOutcome.INVALID_EMAIL,
            before,
        )

    def test_an_address_on_another_site_is_refused(self, mock_site_context):
        organisation = OrganisationFactory()
        User._base_manager.create(site=SiteFactory(), email="away@example.com")

        result = _outcome(organisation, "away@example.com")

        assert result.outcome == AddOutcome.EMAIL_IN_USE_ELSEWHERE

    def test_a_repeated_address_collapses_to_one_result(self, mock_site_context):
        organisation = OrganisationFactory()

        results = add_learners(
            organisation,
            [LearnerEntry("dup@example.com"), LearnerEntry(" DUP@example.com ")],
        )

        assert len(results) == 1

    def test_the_second_run_reports_already_learner_and_already_member(
        self, mock_site_context
    ):
        cohort = CohortFactory()
        entries = [LearnerEntry("again@example.com")]
        add_learners(cohort.organisation, entries, cohort)

        result = add_learners(cohort.organisation, entries, cohort)[0]

        assert (result.outcome, result.cohort_outcome) == (
            AddOutcome.ALREADY_LEARNER,
            CohortOutcome.ALREADY_MEMBER,
        )

    def test_a_cohort_adds_the_new_learner_to_it(self, mock_site_context):
        cohort = CohortFactory()

        result = _outcome(cohort.organisation, "member@example.com", cohort)

        assert result.cohort_outcome == CohortOutcome.ADDED
        assert CohortMembership.objects.filter(
            learner=result.learner, cohort=cohort
        ).exists()

    def test_a_removed_learner_records_a_reactivated_event(
        self, mock_site_context, django_capture_on_commit_callbacks
    ):
        organisation = OrganisationFactory()
        learner = LearnerFactory(organisation=organisation, is_active=False)

        with django_capture_on_commit_callbacks(execute=True):
            _outcome(organisation, learner.user.email)

        event = WebhookEvent._base_manager.get()
        assert event.event_type == "learner.reactivated"

    def test_a_new_learner_records_an_added_event_with_account_created(
        self, mock_site_context, django_capture_on_commit_callbacks
    ):
        organisation = OrganisationFactory()

        with django_capture_on_commit_callbacks(execute=True):
            result = _outcome(organisation, "fresh@example.com")

        event = WebhookEvent._base_manager.get()
        assert event.event_type == "learner.added"
        assert event.payload == {
            "user_id": result.learner.user.pk,
            "user_email": "fresh@example.com",
            "organisation_id": str(organisation.pk),
            "learner_id": str(result.learner.pk),
            "account_created": True,
        }

    def test_an_existing_user_joining_records_account_created_false(
        self, mock_site_context, django_capture_on_commit_callbacks
    ):
        organisation = OrganisationFactory()
        UserFactory(email="known@example.com")

        with django_capture_on_commit_callbacks(execute=True):
            _outcome(organisation, "known@example.com")

        event = WebhookEvent._base_manager.get(event_type="learner.added")
        assert event.payload["account_created"] is False

    def test_a_cohort_records_one_member_added_event_without_a_move_id(
        self, mock_site_context, django_capture_on_commit_callbacks
    ):
        cohort = CohortFactory()

        with django_capture_on_commit_callbacks(execute=True):
            _outcome(cohort.organisation, "member@example.com", cohort)

        event = WebhookEvent._base_manager.get(event_type="cohort_membership.added")
        assert event.payload["move_id"] is None

    def test_a_second_run_records_no_member_added_event(
        self, mock_site_context, django_capture_on_commit_callbacks
    ):
        cohort = CohortFactory()
        _outcome(cohort.organisation, "member@example.com", cohort)
        WebhookEvent._base_manager.all().delete()

        with django_capture_on_commit_callbacks(execute=True):
            _outcome(cohort.organisation, "member@example.com", cohort)

        assert WebhookEvent._base_manager.count() == 0

    def test_an_inactive_cohort_raises_before_any_entry_is_touched(
        self, mock_site_context
    ):
        cohort = CohortFactory(is_active=False)

        with pytest.raises(ValueError, match="active cohort"):
            _outcome(cohort.organisation, "late@example.com", cohort)

        assert not User._base_manager.filter(email="late@example.com").exists()

    def test_another_organisations_cohort_raises_before_any_entry_is_touched(
        self, mock_site_context
    ):
        cohort = CohortFactory(organisation=OrganisationFactory())

        with pytest.raises(ValueError, match="active cohort"):
            _outcome(OrganisationFactory(), "late@example.com", cohort)

        assert not User._base_manager.filter(email="late@example.com").exists()


@pytest.mark.django_db
class TestMoveBetweenCohorts:
    def _setup(self):
        source = CohortFactory()
        destination = CohortFactory(organisation=source.organisation)
        learner = LearnerFactory(organisation=source.organisation)
        CohortMembershipFactory(cohort=source, learner=learner)
        return learner, source, destination

    def test_deletes_the_source_membership(self, mock_site_context):
        learner, source, destination = self._setup()

        move_between_cohorts(learner, source, destination)

        assert not CohortMembership.objects.filter(
            learner=learner, cohort=source
        ).exists()

    def test_creates_the_destination_membership(self, mock_site_context):
        learner, source, destination = self._setup()

        move_between_cohorts(learner, source, destination)

        assert CohortMembership.objects.filter(
            learner=learner, cohort=destination
        ).exists()

    def test_records_removed_then_added_with_the_returned_move_id(
        self, mock_site_context, django_capture_on_commit_callbacks
    ):
        learner, source, destination = self._setup()

        with django_capture_on_commit_callbacks(execute=True):
            move_id = move_between_cohorts(learner, source, destination)

        events = list(WebhookEvent._base_manager.order_by("created_at"))
        assert [
            (e.event_type, e.payload["cohort_id"], e.payload["move_id"]) for e in events
        ] == [
            ("cohort_membership.removed", str(source.pk), move_id),
            ("cohort_membership.added", str(destination.pk), move_id),
        ]

    def test_refuses_the_same_cohort(self, mock_site_context):
        learner, source, _ = self._setup()

        with pytest.raises(ValueError, match="same"):
            move_between_cohorts(learner, source, source)

    def test_refuses_another_organisations_destination_and_changes_nothing(
        self, mock_site_context
    ):
        learner, source, _ = self._setup()
        elsewhere = CohortFactory(organisation=OrganisationFactory())

        with pytest.raises(ValueError, match="another organisation"):
            move_between_cohorts(learner, source, elsewhere)

        assert CohortMembership.objects.get(learner=learner).cohort_id == source.pk

    def test_refuses_an_inactive_source_and_changes_nothing(self, mock_site_context):
        learner, source, destination = self._setup()
        source.is_active = False
        source.save()

        with pytest.raises(ValueError, match="inactive"):
            move_between_cohorts(learner, source, destination)

        assert CohortMembership.objects.get(learner=learner).cohort_id == source.pk

    def test_refuses_an_inactive_destination_and_changes_nothing(
        self, mock_site_context
    ):
        learner, source, destination = self._setup()
        destination.is_active = False
        destination.save()

        with pytest.raises(ValueError, match="inactive"):
            move_between_cohorts(learner, source, destination)

        assert CohortMembership.objects.get(learner=learner).cohort_id == source.pk

    def test_refuses_a_missing_source_membership_and_changes_nothing(
        self, mock_site_context
    ):
        learner, source, destination = self._setup()
        other = CohortFactory(organisation=source.organisation)

        with pytest.raises(ValueError, match="not a member of the source"):
            move_between_cohorts(learner, other, destination)

        assert CohortMembership.objects.get(learner=learner).cohort_id == source.pk

    def test_refuses_an_existing_destination_membership_and_changes_nothing(
        self, mock_site_context
    ):
        learner, source, destination = self._setup()
        CohortMembershipFactory(cohort=destination, learner=learner)

        with pytest.raises(ValueError, match="already a member"):
            move_between_cohorts(learner, source, destination)

        assert CohortMembership.objects.filter(learner=learner).count() == 2

    def test_a_repeated_move_raises(self, mock_site_context):
        learner, source, destination = self._setup()
        move_between_cohorts(learner, source, destination)

        with pytest.raises(ValueError, match="not a member of the source"):
            move_between_cohorts(learner, source, destination)


@pytest.mark.django_db
class TestRegisterForCourse:
    def test_creates_the_registration_and_returns_true(self, mock_site_context):
        learner = LearnerFactory()
        course = CourseFactory()

        created = register_for_course(learner, course)

        assert created is True
        assert LearnerCourseRegistration.objects.filter(
            learner=learner, course=course, is_active=True
        ).exists()

    def test_a_repeat_returns_false(self, mock_site_context):
        learner = LearnerFactory()
        course = CourseFactory()
        register_for_course(learner, course)

        assert register_for_course(learner, course) is False

    def test_reactivates_an_inactive_registration(self, mock_site_context):
        registration = LearnerCourseRegistrationFactory(is_active=False)

        changed = register_for_course(registration.learner, registration.course)

        registration.refresh_from_db()
        assert (changed, registration.is_active) == (True, True)

    def test_locks_the_learner_row_before_deciding_whether_anything_changed(
        self, mock_site_context
    ):
        learner = LearnerFactory()

        with CaptureQueriesContext(connection) as captured:
            register_for_course(learner, CourseFactory())

        assert _locks_the_learner_row(captured)


def _locks_the_learner_row(captured: CaptureQueriesContext) -> bool:
    return any(
        'freedom_ls_learner_management_learner"' in query["sql"]
        and "FOR UPDATE" in query["sql"]
        for query in captured.captured_queries
    )


@pytest.mark.django_db
class TestUnregisterFromCourse:
    def test_deactivates_the_registration_and_returns_true(self, mock_site_context):
        registration = LearnerCourseRegistrationFactory(is_active=True)

        changed = deactivate_registration(registration.learner, registration.course)

        registration.refresh_from_db()
        assert (changed, registration.is_active) == (True, False)

    def test_locks_the_learner_row_before_deciding_whether_anything_changed(
        self, mock_site_context
    ):
        registration = LearnerCourseRegistrationFactory(is_active=True)

        with CaptureQueriesContext(connection) as captured:
            deactivate_registration(registration.learner, registration.course)

        assert _locks_the_learner_row(captured)

    def test_records_a_course_unregistered_event_with_the_payload(
        self, mock_site_context, django_capture_on_commit_callbacks
    ):
        registration = LearnerCourseRegistrationFactory(is_active=True)
        learner, course = registration.learner, registration.course
        WebhookEvent._base_manager.all().delete()

        with django_capture_on_commit_callbacks(execute=True):
            deactivate_registration(learner, course)

        event = WebhookEvent._base_manager.get(event_type="registration.deactivated")
        assert event.payload == {
            "user_id": learner.user.pk,
            "user_email": learner.user.email,
            "organisation_id": str(learner.organisation_id),
            "learner_id": str(learner.pk),
            "course_id": str(course.pk),
            "course_title": course.title,
        }

    def test_a_repeat_returns_false_and_records_nothing(
        self, mock_site_context, django_capture_on_commit_callbacks
    ):
        registration = LearnerCourseRegistrationFactory(is_active=False)
        WebhookEvent._base_manager.all().delete()

        with django_capture_on_commit_callbacks(execute=True):
            changed = deactivate_registration(registration.learner, registration.course)

        assert (changed, WebhookEvent._base_manager.count()) == (False, 0)


@pytest.mark.django_db
class TestRegisterForCourseOrganisationCheck:
    def test_a_course_closed_to_the_learners_organisation_is_refused(
        self, mock_site_context
    ):
        learner = LearnerFactory()
        course = CourseFactory(audience=CourseAudience.ORGANISATION_LEARNERS)
        course.organisations.add(OrganisationFactory())

        with pytest.raises(CourseNotOpenError):
            register_for_course(learner, course)

        assert not LearnerCourseRegistration.objects.filter(learner=learner).exists()
