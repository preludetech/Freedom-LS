"""Tests for the functions that change an application's state."""

from __future__ import annotations

import pytest
import time_machine

from django.utils import timezone

from freedom_ls.audit_log.models import AuditLogEntry
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.course_applications"):
    pytest.skip("course_applications not installed", allow_module_level=True)

from freedom_ls.course_applications.exceptions import ApplicationStateError
from freedom_ls.course_applications.factories import CourseApplicationFactory
from freedom_ls.course_applications.models import CourseApplication
from freedom_ls.course_applications.transitions import (
    submit_application,
    withdraw_application,
)

from .helpers import run_in_parallel_threads

State = CourseApplication.State


@pytest.mark.django_db
class TestSubmitApplication:
    def test_submit_from_draft_sets_state_and_timestamp(self, mock_site_context):
        application = CourseApplicationFactory(state=State.DRAFT)

        with time_machine.travel("2026-03-01 10:00:00+00:00", tick=False):
            submit_application(application)

        application.refresh_from_db()
        assert application.state == State.SUBMITTED
        assert application.submitted_at == timezone.now().replace(
            year=2026, month=3, day=1, hour=10, minute=0, second=0, microsecond=0
        )

    def test_submit_moves_updated_at(self, mock_site_context):
        application = CourseApplicationFactory(state=State.DRAFT)
        before = application.updated_at

        submit_application(application)

        application.refresh_from_db()
        assert application.updated_at > before

    def test_submit_updates_the_instance_it_was_given(self, mock_site_context):
        application = CourseApplicationFactory(state=State.DRAFT)

        returned = submit_application(application)

        assert returned is application
        assert application.state == State.SUBMITTED
        assert application.submitted_at is not None

    def test_submit_writes_no_audit_entry(self, mock_site_context):
        application = CourseApplicationFactory(state=State.DRAFT)

        submit_application(application)

        assert not AuditLogEntry.objects.exists()

    @pytest.mark.parametrize(
        "trait",
        [{}, {"approved": True}, {"rejected": True}, {"withdrawn": True}],
        ids=["submitted", "approved", "rejected", "withdrawn"],
    )
    def test_submit_from_any_other_state_raises_and_changes_nothing(
        self, mock_site_context, trait
    ):
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
        self, mock_site_context, trait
    ):
        application = CourseApplicationFactory(**trait)

        with time_machine.travel("2026-03-01 10:00:00+00:00", tick=False):
            withdraw_application(application)

        application.refresh_from_db()
        assert application.state == State.WITHDRAWN
        assert application.withdrawn_at == timezone.now().replace(
            year=2026, month=3, day=1, hour=10, minute=0, second=0, microsecond=0
        )

    def test_withdraw_moves_updated_at(self, mock_site_context):
        application = CourseApplicationFactory()
        before = application.updated_at

        withdraw_application(application)

        application.refresh_from_db()
        assert application.updated_at > before

    def test_withdraw_writes_no_audit_entry(self, mock_site_context):
        application = CourseApplicationFactory()

        withdraw_application(application)

        assert not AuditLogEntry.objects.exists()

    @pytest.mark.parametrize(
        "trait",
        [{"approved": True}, {"rejected": True}, {"withdrawn": True}],
        ids=["approved", "rejected", "withdrawn"],
    )
    def test_withdraw_from_any_other_state_raises_and_changes_nothing(
        self, mock_site_context, trait
    ):
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
def test_withdraw_racing_withdraws_succeed_exactly_once(mock_site_context):
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
