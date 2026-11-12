from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import time_machine

from django.db import transaction

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.audit_log.models import REASON_LENGTH, AuditLogEntry
from freedom_ls.comms.models import Notification
from freedom_ls.deadlines.actions import (
    DeadlineActionError,
    pause_course,
    resume_course,
)
from freedom_ls.deadlines.factories import CoursePauseFactory
from freedom_ls.deadlines.models import CoursePause
from freedom_ls.learner_management.models import LearnerCourseRegistration
from freedom_ls.learner_progress.factories import CourseProgressFactory
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.site_aware_models.factories import SiteTimeZoneConfigFactory
from freedom_ls.tests.audit_assertions import assert_entry

NOW = datetime(2026, 3, 10, 10, 0, tzinfo=UTC)


_fired: list[MagicMock] = []


@pytest.fixture(autouse=True)
def _webhook_dispatch() -> Iterator[None]:
    """Stand in for the dispatcher that runs on commit, so a test sees what would be sent."""
    with patch("freedom_ls.webhooks.events.fire_webhook_event") as dispatch:
        _fired[:] = [dispatch]
        yield


def _then_roll_back(action: Callable[[], object]) -> None:
    with transaction.atomic():
        action()
        raise RuntimeError


def _events(event_type: str) -> list[SimpleNamespace]:
    return [
        SimpleNamespace(payload=call.args[1])
        for call in _fired[0].call_args_list
        if call.args[0] == event_type
    ]


@pytest.mark.django_db
class TestPauseCourse:
    def test_creates_an_open_pause_on_the_records_site(self, mock_site_context):
        record = CourseProgressFactory()
        actor = UserFactory()

        pause = pause_course(record, actor=actor, reason="  On leave ", now=NOW)

        assert (
            pause.site_id,
            pause.course_progress_id,
            pause.started_at,
            pause.ended_at,
            pause.reason,
            pause.started_by,
        ) == (record.site_id, record.pk, NOW, None, "On leave", actor)

    def test_writes_one_audit_entry_for_the_learner(self, mock_site_context):
        record: CourseProgress = CourseProgressFactory()
        actor = UserFactory()

        pause_course(
            record,
            actor=actor,
            reason="On leave",
            planned_resume_on=date(2026, 3, 20),
            now=NOW,
        )

        assert_entry(
            action="course.paused",
            actor=actor,
            target=record.learner,
            target_label=record.learner.user.display_name,
            organisation=record.learner.organisation,
            subjects=[record.course],
            details={
                "course": record.course.title,
                "planned_resume_on": "2026-03-20",
            },
            reason="On leave",
        )

    def test_fires_one_webhook_after_commit(
        self, mock_site_context, django_capture_on_commit_callbacks
    ):
        record = CourseProgressFactory()
        actor = UserFactory()

        with django_capture_on_commit_callbacks(execute=True):
            pause = pause_course(
                record,
                actor=actor,
                reason="On leave",
                planned_resume_on=date(2026, 3, 20),
                now=NOW,
            )

        (event,) = _events("course.paused")
        assert event.payload["pause_id"] == str(pause.pk)
        assert event.payload["actor_id"] == str(actor.pk)
        assert event.payload["paused_at"] == NOW.isoformat()
        assert event.payload["course_progress_id"] == str(record.pk)
        assert event.payload["planned_resume_at"] is not None

    def test_the_webhook_does_not_fire_before_commit(self, mock_site_context):
        record = CourseProgressFactory()

        pause_course(record, actor=UserFactory(), reason="On leave", now=NOW)

        assert _events("course.paused") == []

    def test_notifies_the_learner_once(
        self, mock_site_context, django_capture_on_commit_callbacks
    ):
        record = CourseProgressFactory()

        with django_capture_on_commit_callbacks(execute=True):
            pause_course(record, actor=UserFactory(), reason="Private", now=NOW)

        notification = Notification.objects.get()
        assert (notification.user, notification.category) == (
            record.learner.user,
            "course.paused",
        )
        assert "Private" not in str(notification.data)

    def test_the_learner_acting_gets_no_notification_but_the_webhook_fires(
        self, mock_site_context, django_capture_on_commit_callbacks
    ):
        record = CourseProgressFactory()

        with django_capture_on_commit_callbacks(execute=True):
            pause_course(record, actor=record.learner.user, reason="Away", now=NOW)

        assert Notification.objects.count() == 0
        assert len(_events("course.paused")) == 1

    def test_no_payload_carries_the_reason(
        self, mock_site_context, django_capture_on_commit_callbacks
    ):
        record = CourseProgressFactory()

        with django_capture_on_commit_callbacks(execute=True):
            pause_course(record, actor=UserFactory(), reason="Hidden words", now=NOW)

        (event,) = _events("course.paused")
        assert "Hidden words" not in str(event.payload)

    def test_a_rolled_back_pause_writes_and_fires_nothing(
        self, mock_site_context, django_capture_on_commit_callbacks
    ):
        record = CourseProgressFactory()

        with (
            django_capture_on_commit_callbacks(execute=True),
            pytest.raises(RuntimeError),
        ):
            _then_roll_back(
                lambda: pause_course(
                    record, actor=UserFactory(), reason="Away", now=NOW
                )
            )

        assert (
            CoursePause._base_manager.count(),
            AuditLogEntry.unscoped.count(),
            Notification.objects.count(),
            len(_events("course.paused")),
        ) == (0, 0, 0, 0)

    @pytest.mark.parametrize(
        "reason",
        ["", "   ", "x" * (REASON_LENGTH + 1)],
        ids=["blank", "whitespace", "too long"],
    )
    def test_refuses_an_unusable_reason(self, mock_site_context, reason):
        record = CourseProgressFactory()

        with pytest.raises(DeadlineActionError):
            pause_course(record, actor=UserFactory(), reason=reason, now=NOW)

    def test_refuses_a_complete_record(self, mock_site_context):
        record = CourseProgressFactory(completed_time=NOW - timedelta(days=1))

        with pytest.raises(DeadlineActionError):
            pause_course(record, actor=UserFactory(), reason="Away", now=NOW)

    def test_refuses_an_already_paused_record(self, mock_site_context):
        record = CourseProgressFactory()
        CoursePauseFactory(course_progress=record, started_at=NOW - timedelta(hours=1))

        with pytest.raises(DeadlineActionError):
            pause_course(record, actor=UserFactory(), reason="Away", now=NOW)

    @pytest.mark.parametrize(
        "planned",
        [date(2026, 3, 10), date(2026, 3, 9)],
        ids=["today", "past"],
    )
    def test_refuses_a_planned_resume_that_is_not_after_today(
        self, mock_site_context, planned
    ):
        record = CourseProgressFactory()

        with pytest.raises(DeadlineActionError):
            pause_course(
                record,
                actor=UserFactory(),
                reason="Away",
                planned_resume_on=planned,
                now=NOW,
            )

    def test_today_is_read_in_the_site_zone(self, mock_site_context):
        SiteTimeZoneConfigFactory(
            site=mock_site_context, time_zone="Africa/Johannesburg"
        )
        record = CourseProgressFactory()
        late = datetime(2026, 3, 10, 23, 0, tzinfo=UTC)

        with pytest.raises(DeadlineActionError):
            pause_course(
                record,
                actor=UserFactory(),
                reason="Away",
                planned_resume_on=date(2026, 3, 11),
                now=late,
            )

    def test_leaves_the_registration_active_and_fires_no_deactivation(
        self, mock_site_context, django_capture_on_commit_callbacks
    ):
        record = CourseProgressFactory()

        with django_capture_on_commit_callbacks(execute=True):
            pause_course(record, actor=UserFactory(), reason="Away", now=NOW)

        assert LearnerCourseRegistration.objects.get(
            pk=record.learner_registration_id
        ).is_active
        assert _events("registration.deactivated") == []

    def test_closes_and_announces_a_passed_planned_pause_then_starts_a_new_one(
        self, mock_site_context, django_capture_on_commit_callbacks
    ):
        record = CourseProgressFactory()
        old = CoursePauseFactory(
            course_progress=record,
            started_at=datetime(2026, 3, 1, 8, 0, tzinfo=UTC),
            planned_resume_on=date(2026, 3, 5),
        )

        with django_capture_on_commit_callbacks(execute=True):
            new = pause_course(record, actor=UserFactory(), reason="Again", now=NOW)

        old.refresh_from_db()
        assert old.ended_at == datetime(2026, 3, 5, tzinfo=UTC)
        assert old.resume_announced_at == NOW
        (resumed,) = _events("course.resumed")
        assert (resumed.payload["planned"], resumed.payload["actor_id"]) == (True, None)
        assert resumed.payload["shift_days"] == 4
        assert new.ended_at is None
        assert new.pk != old.pk
        assert AuditLogEntry.unscoped.filter(action="course.resumed").count() == 1
        assert Notification.objects.filter(category="course.resumed").count() == 1

    def test_no_pause_is_left_for_the_sweep_to_announce_after_it_is_closed(
        self, mock_site_context
    ):
        record = CourseProgressFactory()
        CoursePauseFactory(
            course_progress=record,
            started_at=datetime(2026, 3, 1, 8, 0, tzinfo=UTC),
            planned_resume_on=date(2026, 3, 5),
        )

        pause_course(record, actor=UserFactory(), reason="Again", now=NOW)

        assert not CoursePause._base_manager.filter(
            course_progress=record,
            planned_resume_on__isnull=False,
            resume_announced_at__isnull=True,
        ).exists()


@pytest.mark.django_db
class TestResumeCourse:
    def _paused(self, started: datetime = NOW - timedelta(days=2, hours=3)):
        record = CourseProgressFactory()
        pause = CoursePauseFactory(course_progress=record, started_at=started)
        return record, pause

    def test_ends_the_pause_and_stores_who_why_and_when(self, mock_site_context):
        record, pause = self._paused()
        actor = UserFactory()

        resume_course(record, actor=actor, reason=" Back ", now=NOW)

        pause.refresh_from_db()
        assert (
            pause.ended_at,
            pause.ended_by,
            pause.ended_reason,
            pause.resume_announced_at,
        ) == (NOW, actor, "Back", NOW)

    def test_writes_one_audit_entry_with_the_days_shifted(self, mock_site_context):
        record, _pause = self._paused()
        actor = UserFactory()

        resume_course(record, actor=actor, reason="Back", now=NOW)

        assert_entry(
            action="course.resumed",
            actor=actor,
            target=record.learner,
            target_label=record.learner.user.display_name,
            organisation=record.learner.organisation,
            subjects=[record.course],
            details={"course": record.course.title, "shift_days": 3},
            reason="Back",
        )

    def test_fires_one_webhook_and_one_notification(
        self, mock_site_context, django_capture_on_commit_callbacks
    ):
        record, pause = self._paused()

        with django_capture_on_commit_callbacks(execute=True):
            resume_course(record, actor=UserFactory(), reason="Back now", now=NOW)

        (event,) = _events("course.resumed")
        assert event.payload["shift_days"] == 3
        assert event.payload["planned"] is False
        assert event.payload["pause_id"] == str(pause.pk)
        assert Notification.objects.get().category == "course.resumed"
        assert "Back now" not in str(event.payload)

    def test_the_learner_resuming_gets_no_notification_but_the_webhook_fires(
        self, mock_site_context, django_capture_on_commit_callbacks
    ):
        record, _pause = self._paused()

        with django_capture_on_commit_callbacks(execute=True):
            resume_course(record, actor=record.learner.user, reason="Back", now=NOW)

        assert Notification.objects.count() == 0
        assert len(_events("course.resumed")) == 1

    def test_a_second_call_shifts_and_fires_once(
        self, mock_site_context, django_capture_on_commit_callbacks
    ):
        record, _pause = self._paused()

        with django_capture_on_commit_callbacks(execute=True):
            first = resume_course(record, actor=UserFactory(), reason="Back", now=NOW)
            second = resume_course(record, actor=UserFactory(), reason="Back", now=NOW)

        assert (first is not None, second) == (True, None)
        assert len(_events("course.resumed")) == 1
        assert AuditLogEntry.unscoped.count() == 1

    def test_returns_none_and_writes_nothing_when_not_paused(self, mock_site_context):
        record = CourseProgressFactory()

        result = resume_course(record, actor=UserFactory(), reason="Back", now=NOW)

        assert (result, AuditLogEntry.unscoped.count()) == (None, 0)

    def test_refuses_a_blank_reason(self, mock_site_context):
        record, _pause = self._paused()

        with pytest.raises(DeadlineActionError):
            resume_course(record, actor=UserFactory(), reason=" ", now=NOW)

    def test_a_rolled_back_resume_writes_and_fires_nothing(
        self, mock_site_context, django_capture_on_commit_callbacks
    ):
        record, pause = self._paused()

        with (
            django_capture_on_commit_callbacks(execute=True),
            pytest.raises(RuntimeError),
        ):
            _then_roll_back(
                lambda: resume_course(
                    record, actor=UserFactory(), reason="Back", now=NOW
                )
            )

        pause.refresh_from_db()
        assert (
            pause.ended_at,
            AuditLogEntry.unscoped.count(),
            Notification.objects.count(),
            len(_events("course.resumed")),
        ) == (None, 0, 0, 0)

    def test_a_pause_whose_planned_resume_passed_is_left_to_be_announced(
        self, mock_site_context
    ):
        record = CourseProgressFactory()
        CoursePauseFactory(
            course_progress=record,
            started_at=NOW - timedelta(days=5),
            planned_resume_on=date(2026, 3, 8),
        )

        result = resume_course(record, actor=UserFactory(), reason="Back", now=NOW)

        assert result is None


@time_machine.travel(NOW, tick=False)
@pytest.mark.django_db
def test_now_defaults_to_the_current_instant(mock_site_context):
    record = CourseProgressFactory()

    pause = pause_course(record, actor=UserFactory(), reason="Away")

    assert pause.started_at == NOW
