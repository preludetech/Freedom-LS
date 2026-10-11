from __future__ import annotations

import pytest

from freedom_ls.accounts.factories import SiteFactory, UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.learner_actions import (
    AddOutcome,
    CohortOutcome,
    LearnerEntry,
    add_learners,
    add_to_cohort,
    deactivate_learner,
    move_between_cohorts,
    reactivate_learner,
    remove_from_cohort,
)
from freedom_ls.learner_management.models import (
    CohortMembership,
    Learner,
    LearnerCourseRegistration,
)
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.webhooks.models import WebhookEvent


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
        assert event.event_type == "cohort.member_removed"
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
        assert event.event_type == "cohort.member_added"
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

        event = WebhookEvent._base_manager.get(event_type="cohort.member_added")
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

        events = list(WebhookEvent._base_manager.order_by("pk"))
        assert [
            (e.event_type, e.payload["cohort_id"], e.payload["move_id"]) for e in events
        ] == [
            ("cohort.member_removed", str(source.pk), move_id),
            ("cohort.member_added", str(destination.pk), move_id),
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
