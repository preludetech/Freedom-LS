"""Tests for the functions that change an application's state."""

from __future__ import annotations

import pytest
import time_machine

from django.contrib.sites.models import Site
from django.utils import timezone

from freedom_ls.audit_log.models import AuditLogEntry
from freedom_ls.audit_log.writer import subject_key
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.course_applications"):
    pytest.skip("course_applications not installed", allow_module_level=True)

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.course_applications.exceptions import (
    ApplicationStateError,
    RejectionMessageError,
    UnclaimedApplicationError,
)
from freedom_ls.course_applications.factories import CourseApplicationFactory
from freedom_ls.course_applications.models import (
    REJECTION_MESSAGE_MAX_LENGTH,
    CourseApplication,
)
from freedom_ls.course_applications.transitions import (
    approve_application,
    reject_application,
    submit_application,
    withdraw_application,
)

from .helpers import (
    APPLICATION_IN_STATE,
    TRANSITION_CALLS,
    TRANSITION_RESULTS,
    run_in_parallel_threads,
)

State = CourseApplication.State

_ALLOWED_PAIRS = [
    ("submit_application", "draft"),
    ("withdraw_application", "draft"),
    ("withdraw_application", "submitted"),
    ("approve_application", "submitted"),
    ("reject_application", "submitted"),
]
_REFUSED_PAIRS = [
    (function, state)
    for function in TRANSITION_CALLS
    for state in APPLICATION_IN_STATE
    if (function, state) not in _ALLOWED_PAIRS
]


def _pair_id(pair: tuple[str, str]) -> str:
    return f"{pair[0].removesuffix('_application')}-from-{pair[1]}"


@pytest.mark.django_db
class TestSubmitApplication:
    def test_submit_from_draft_sets_state_and_timestamp(
        self, mock_site_context: Site
    ) -> None:
        application = CourseApplicationFactory(state=State.DRAFT)

        with time_machine.travel("2026-03-01 10:00:00+00:00", tick=False):
            submit_application(application)

        application.refresh_from_db()
        assert application.state == State.SUBMITTED
        assert application.submitted_at == timezone.now().replace(
            year=2026, month=3, day=1, hour=10, minute=0, second=0, microsecond=0
        )

    def test_submit_moves_updated_at(self, mock_site_context: Site) -> None:
        application = CourseApplicationFactory(state=State.DRAFT)
        before = application.updated_at

        submit_application(application)

        application.refresh_from_db()
        assert application.updated_at > before

    def test_submit_updates_the_instance_it_was_given(
        self, mock_site_context: Site
    ) -> None:
        application = CourseApplicationFactory(state=State.DRAFT)

        returned = submit_application(application)

        assert returned is application
        assert application.state == State.SUBMITTED
        assert application.submitted_at is not None

    def test_submit_writes_no_audit_entry(self, mock_site_context: Site) -> None:
        application = CourseApplicationFactory(state=State.DRAFT)

        submit_application(application)

        assert not AuditLogEntry.objects.exists()

    @pytest.mark.parametrize(
        "trait",
        [{}, {"approved": True}, {"rejected": True}, {"withdrawn": True}],
        ids=["submitted", "approved", "rejected", "withdrawn"],
    )
    def test_submit_from_any_other_state_raises_and_changes_nothing(
        self, mock_site_context: Site, trait: dict[str, bool]
    ) -> None:
        application = CourseApplicationFactory(course=CourseFactory(), **trait)
        current_state = application.state
        before = CourseApplication.objects.get(pk=application.pk)

        with pytest.raises(ApplicationStateError) as raised:
            submit_application(application)

        after = CourseApplication.objects.get(pk=application.pk)
        assert raised.value.current_state == current_state
        assert after.state == current_state
        assert after.updated_at == before.updated_at


@pytest.mark.django_db
class TestWithdrawApplication:
    @pytest.mark.parametrize(
        "trait",
        [{"state": State.DRAFT, "submitted_at": None}, {}],
        ids=["draft", "submitted"],
    )
    def test_withdraw_from_an_open_state_sets_state_and_timestamp(
        self, mock_site_context: Site, trait: dict[str, object]
    ) -> None:
        application = CourseApplicationFactory(**trait)

        with time_machine.travel("2026-03-01 10:00:00+00:00", tick=False):
            withdraw_application(application)

        application.refresh_from_db()
        assert application.state == State.WITHDRAWN
        assert application.withdrawn_at == timezone.now().replace(
            year=2026, month=3, day=1, hour=10, minute=0, second=0, microsecond=0
        )

    def test_withdraw_moves_updated_at(self, mock_site_context: Site) -> None:
        application = CourseApplicationFactory()
        before = application.updated_at

        withdraw_application(application)

        application.refresh_from_db()
        assert application.updated_at > before

    def test_withdraw_writes_no_audit_entry(self, mock_site_context: Site) -> None:
        application = CourseApplicationFactory()

        withdraw_application(application)

        assert not AuditLogEntry.objects.exists()

    @pytest.mark.parametrize(
        "trait",
        [{"approved": True}, {"rejected": True}, {"withdrawn": True}],
        ids=["approved", "rejected", "withdrawn"],
    )
    def test_withdraw_from_any_other_state_raises_and_changes_nothing(
        self, mock_site_context: Site, trait: dict[str, bool]
    ) -> None:
        application = CourseApplicationFactory(course=CourseFactory(), **trait)
        current_state = application.state
        before = CourseApplication.objects.get(pk=application.pk)

        with pytest.raises(ApplicationStateError) as raised:
            withdraw_application(application)

        after = CourseApplication.objects.get(pk=application.pk)
        assert raised.value.current_state == current_state
        assert after.state == current_state
        assert after.withdrawn_at == before.withdrawn_at
        assert after.updated_at == before.updated_at


@pytest.mark.django_db(transaction=True)
def test_withdraw_racing_withdraws_succeed_exactly_once(
    mock_site_context: Site,
) -> None:
    """transaction=True so each thread's own connection sees the other's commit."""
    application = CourseApplicationFactory()

    outcomes = run_in_parallel_threads(
        mock_site_context,
        lambda: withdraw_application(CourseApplication.objects.get(pk=application.pk)),
        count=2,
    )

    failures = [o for o in outcomes if o is not None]
    assert len(failures) == 1
    assert isinstance(failures[0], ApplicationStateError)


@pytest.mark.django_db
class TestEveryTransition:
    @pytest.mark.parametrize(("function", "state"), _ALLOWED_PAIRS, ids=_pair_id)
    def test_an_allowed_move_writes_state_and_timestamp(
        self, mock_site_context: Site, function: str, state: str
    ) -> None:
        application = CourseApplicationFactory(**APPLICATION_IN_STATE[state])
        new_state, stamp_field = TRANSITION_RESULTS[function]

        with time_machine.travel("2026-03-01 10:00:00+00:00", tick=False):
            TRANSITION_CALLS[function](application)
            expected_stamp = timezone.now()

        stored = CourseApplication.objects.get(pk=application.pk)
        assert stored.state == new_state
        assert getattr(stored, stamp_field) == expected_stamp

    @pytest.mark.parametrize(("function", "state"), _ALLOWED_PAIRS, ids=_pair_id)
    def test_an_allowed_move_moves_updated_at(
        self, mock_site_context: Site, function: str, state: str
    ) -> None:
        application = CourseApplicationFactory(**APPLICATION_IN_STATE[state])
        before = application.updated_at

        TRANSITION_CALLS[function](application)

        assert CourseApplication.objects.get(pk=application.pk).updated_at > before

    @pytest.mark.parametrize(("function", "state"), _ALLOWED_PAIRS, ids=_pair_id)
    def test_an_allowed_move_updates_the_instance_it_was_given(
        self, mock_site_context: Site, function: str, state: str
    ) -> None:
        application = CourseApplicationFactory(**APPLICATION_IN_STATE[state])
        new_state, stamp_field = TRANSITION_RESULTS[function]

        returned = TRANSITION_CALLS[function](application)

        assert returned is application
        assert application.state == new_state
        assert getattr(application, stamp_field) is not None

    @pytest.mark.parametrize(("function", "state"), _REFUSED_PAIRS, ids=_pair_id)
    def test_a_refused_move_raises_and_leaves_row_and_audit_log_untouched(
        self, mock_site_context: Site, function: str, state: str
    ) -> None:
        application = CourseApplicationFactory(
            course=CourseFactory(), **APPLICATION_IN_STATE[state]
        )
        before = CourseApplication.objects.get(pk=application.pk)

        with pytest.raises(ApplicationStateError) as raised:
            TRANSITION_CALLS[function](application)

        after = CourseApplication.objects.get(pk=application.pk)
        assert raised.value.current_state == state
        assert after.state == before.state
        assert after.updated_at == before.updated_at
        assert not AuditLogEntry.objects.exists()


@pytest.mark.django_db
class TestApproveApplication:
    def test_approve_of_an_unclaimed_application_raises_and_writes_nothing(
        self, mock_site_context: Site
    ) -> None:
        application = CourseApplicationFactory(anonymous=True)
        before = CourseApplication.objects.get(pk=application.pk)

        with pytest.raises(UnclaimedApplicationError):
            approve_application(application, actor=UserFactory())

        after = CourseApplication.objects.get(pk=application.pk)
        assert after.state == State.SUBMITTED
        assert after.updated_at == before.updated_at
        assert not AuditLogEntry.objects.exists()


@pytest.mark.django_db
class TestRejectApplication:
    def test_reject_of_an_unclaimed_application_succeeds_and_keeps_it_unclaimed(
        self, mock_site_context: Site
    ) -> None:
        application = CourseApplicationFactory(anonymous=True)

        reject_application(application, actor=UserFactory(), message="Not this time.")

        application.refresh_from_db()
        assert application.state == State.REJECTED
        assert application.user_id is None

    @pytest.mark.parametrize(
        "message",
        ["", "   ", "x" * (REJECTION_MESSAGE_MAX_LENGTH + 1)],
        ids=["empty", "blank", "too-long"],
    )
    def test_reject_with_an_unusable_message_raises_and_writes_nothing(
        self, mock_site_context: Site, message: str
    ) -> None:
        application = CourseApplicationFactory()
        before = CourseApplication.objects.get(pk=application.pk)

        with pytest.raises(RejectionMessageError):
            reject_application(application, actor=UserFactory(), message=message)

        after = CourseApplication.objects.get(pk=application.pk)
        assert after.state == State.SUBMITTED
        assert after.updated_at == before.updated_at
        assert not AuditLogEntry.objects.exists()

    def test_reject_with_a_message_of_exactly_the_cap_succeeds(
        self, mock_site_context: Site
    ) -> None:
        application = CourseApplicationFactory()

        reject_application(
            application,
            actor=UserFactory(),
            message="x" * REJECTION_MESSAGE_MAX_LENGTH,
        )

        application.refresh_from_db()
        assert application.state == State.REJECTED

    def test_reject_stores_the_message_stripped(self, mock_site_context: Site) -> None:
        application = CourseApplicationFactory()

        reject_application(
            application, actor=UserFactory(), message="  Not this time.  "
        )

        application.refresh_from_db()
        assert application.rejection_message == "Not this time."

    def test_reject_checks_the_cap_on_the_stripped_message(
        self, mock_site_context: Site
    ) -> None:
        application = CourseApplicationFactory()
        message = f" {'x' * REJECTION_MESSAGE_MAX_LENGTH} "

        reject_application(application, actor=UserFactory(), message=message)

        application.refresh_from_db()
        assert application.state == State.REJECTED


@pytest.mark.django_db
class TestDecisionAudit:
    @pytest.mark.parametrize(
        ("function", "action", "to"),
        [
            ("approve_application", "application.approved", "approved"),
            ("reject_application", "application.rejected", "rejected"),
        ],
        ids=["approve", "reject"],
    )
    def test_a_decision_writes_exactly_one_entry_naming_the_move(
        self, mock_site_context: Site, function: str, action: str, to: str
    ) -> None:
        application = CourseApplicationFactory()

        TRANSITION_CALLS[function](application)

        entry = AuditLogEntry.objects.get()
        assert entry.action == action
        assert entry.details == {"from": "submitted", "to": to}
        assert entry.organisation == application.organisation
        assert entry.subjects == [
            subject_key(application),
            subject_key(application.course),
        ]

    def test_an_approval_entry_is_attributed_to_the_reviewer(
        self, mock_site_context: Site
    ) -> None:
        reviewer = UserFactory()
        application = CourseApplicationFactory()

        approve_application(application, actor=reviewer)

        assert AuditLogEntry.objects.get().actor == reviewer

    def test_a_rejection_entry_is_attributed_to_the_reviewer(
        self, mock_site_context: Site
    ) -> None:
        reviewer = UserFactory()
        application = CourseApplicationFactory()

        reject_application(application, actor=reviewer, message="Not this time.")

        assert AuditLogEntry.objects.get().actor == reviewer

    def test_a_rejection_entry_holds_neither_applicant_nor_message(
        self, mock_site_context: Site
    ) -> None:
        applicant = UserFactory(first_name="Zelda", last_name="Zebra")
        application = CourseApplicationFactory(user=applicant)

        reject_application(
            application, actor=UserFactory(), message="Secret reviewer wording"
        )

        entry = AuditLogEntry.objects.get()
        text = f"{entry.target_label} {entry.details} {entry.reason}".lower()
        assert applicant.email.lower() not in text
        assert "zelda" not in text
        assert "secret reviewer wording" not in text
