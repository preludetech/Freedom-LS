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
from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.content_engine.models import ContentCollectionItem, Course
from freedom_ls.content_engine.tests.helpers import collection_item_for
from freedom_ls.deadlines.actions import (
    DeadlineActionError,
    announce_planned_resume,
    extend_deadline,
    pause_course,
    resume_course,
)
from freedom_ls.deadlines.factories import (
    CoursePauseFactory,
    DeadlineExtensionFactory,
    SiteDeadlineConfigFactory,
)
from freedom_ls.deadlines.models import (
    MAX_EXTENSION_DAYS,
    CoursePause,
    DeadlineExtension,
    ExtensionTarget,
)
from freedom_ls.deadlines.resolver import course_deadlines
from freedom_ls.learner_management.models import LearnerCourseRegistration
from freedom_ls.learner_progress.factories import CourseProgressFactory
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.learner_progress.tests.helpers import course_progress_record
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

    def test_succeeds_whatever_the_pause_limits_and_switch_say(self, mock_site_context):
        SiteDeadlineConfigFactory(
            learners_may_pause="off", max_pauses=1, max_pause_days=1
        )
        record = CourseProgressFactory()
        CoursePauseFactory(
            course_progress=record,
            started_at=datetime(2026, 1, 1, tzinfo=UTC),
            ended_at=datetime(2026, 2, 1, tzinfo=UTC),
        )

        pause = pause_course(record, actor=UserFactory(), reason="Away", now=NOW)

        assert pause.ended_at is None

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


@pytest.mark.django_db
class TestAnnouncePlannedResume:
    def _due_pause(self, **kwargs: object) -> CoursePause:
        defaults: dict[str, object] = {
            "started_at": datetime(2026, 3, 1, 8, 0, tzinfo=UTC),
            "planned_resume_on": date(2026, 3, 5),
        }
        pause: CoursePause = CoursePauseFactory(**{**defaults, **kwargs})
        return pause

    def test_announces_once_under_two_callers(
        self, mock_site_context, django_capture_on_commit_callbacks
    ):
        pause = self._due_pause()

        with django_capture_on_commit_callbacks(execute=True):
            first = announce_planned_resume(pause, now=NOW)
            second = announce_planned_resume(pause, now=NOW)

        assert (first, second) == (True, False)
        assert AuditLogEntry.unscoped.filter(action="course.resumed").count() == 1
        assert len(_events("course.resumed")) == 1
        assert Notification.objects.filter(category="course.resumed").count() == 1
        pause.refresh_from_db()
        assert pause.resume_announced_at == NOW

    def test_the_second_caller_with_a_stale_copy_announces_nothing(
        self, mock_site_context
    ):
        pause = self._due_pause()
        stale = CoursePause._base_manager.get(pk=pause.pk)

        announce_planned_resume(pause, now=NOW)
        result = announce_planned_resume(stale, now=NOW)

        assert result is False
        assert AuditLogEntry.unscoped.filter(action="course.resumed").count() == 1

    def test_records_the_end_at_the_planned_instant(self, mock_site_context):
        pause = self._due_pause()

        announce_planned_resume(pause, now=NOW)

        pause.refresh_from_db()
        assert pause.ended_at == datetime(2026, 3, 5, tzinfo=UTC)
        assert AuditLogEntry.unscoped.get(action="course.resumed").actor is None

    def test_keeps_an_end_staff_already_recorded(self, mock_site_context):
        ended = datetime(2026, 3, 3, tzinfo=UTC)
        pause = self._due_pause(ended_at=ended)

        announce_planned_resume(pause, now=NOW)

        pause.refresh_from_db()
        assert pause.ended_at == ended

    @pytest.mark.parametrize(
        "overrides",
        [
            {"resume_announced_at": datetime(2026, 3, 6, tzinfo=UTC)},
            {"planned_resume_on": date(2026, 3, 11)},
            {"planned_resume_on": None},
        ],
        ids=["already-announced", "not-yet-due", "no-planned-resume"],
    )
    def test_skips_a_pause_that_is_not_due(self, mock_site_context, overrides):
        pause = self._due_pause(**overrides)

        result = announce_planned_resume(pause, now=NOW)

        assert result is False
        assert AuditLogEntry.unscoped.filter(action="course.resumed").count() == 0
        assert Notification.objects.filter(category="course.resumed").count() == 0

    def test_skips_a_pause_staff_ended_early(self, mock_site_context):
        record = CourseProgressFactory()
        pause = self._due_pause(
            course_progress=record, planned_resume_on=date(2026, 3, 11)
        )
        resume_course(record, actor=UserFactory(), reason="Back", now=NOW)
        pause.refresh_from_db()

        result = announce_planned_resume(pause, now=NOW + timedelta(days=2))

        assert result is False
        assert AuditLogEntry.unscoped.filter(action="course.resumed").count() == 1

    def test_now_defaults_to_the_current_instant(self, mock_site_context):
        pause = self._due_pause()

        with time_machine.travel(NOW, tick=False):
            announce_planned_resume(pause)

        pause.refresh_from_db()
        assert pause.resume_announced_at == NOW


@time_machine.travel(NOW, tick=False)
@pytest.mark.django_db
def test_now_defaults_to_the_current_instant(mock_site_context):
    record = CourseProgressFactory()

    pause = pause_course(record, actor=UserFactory(), reason="Away")

    assert pause.started_at == NOW


DUE = date(2026, 3, 20)


def _record_with_a_dated_topic(
    due_date: date | None = DUE, time_limit_days: int | None = None
) -> tuple[CourseProgress, ContentCollectionItem]:
    course: Course = CourseFactory(time_limit_days=time_limit_days)
    topic = TopicFactory()
    course.items.create(child=topic, order=0)
    item = collection_item_for(course, topic)
    item.due_date = due_date
    item.save()
    return course_progress_record(course, UserFactory(), created_at=NOW), item


def _item_due(record: CourseProgress, item: ContentCollectionItem) -> datetime:
    due_at = course_deadlines(record, now=NOW).items[item.pk].due_at
    assert due_at is not None
    return due_at


@pytest.mark.django_db
class TestExtendDeadline:
    def test_an_item_extension_by_days_stores_the_row_and_moves_the_deadline(
        self, mock_site_context
    ):
        record, item = _record_with_a_dated_topic()
        actor = UserFactory()
        due_before = _item_due(record, item)

        extension = extend_deadline(
            record,
            actor=actor,
            reason="  Was ill ",
            target_kind=ExtensionTarget.COLLECTION_ITEM,
            collection_item=item,
            days=4,
            now=NOW,
        )

        assert (
            extension.site_id,
            extension.course_progress_id,
            extension.target_kind,
            extension.collection_item,
            extension.days,
            extension.requested_date,
            extension.reason,
            extension.set_by,
        ) == (
            record.site_id,
            record.pk,
            ExtensionTarget.COLLECTION_ITEM,
            item,
            4,
            None,
            "Was ill",
            actor,
        )
        assert _item_due(record, item) == due_before + timedelta(days=4)

    def test_a_date_converts_to_days_against_the_effective_instant(
        self, mock_site_context
    ):
        record, item = _record_with_a_dated_topic()
        DeadlineExtensionFactory(
            course_progress=record,
            target_kind=ExtensionTarget.COLLECTION_ITEM,
            collection_item=item,
            days=3,
        )

        extension = extend_deadline(
            record,
            actor=UserFactory(),
            reason="Late",
            target_kind=ExtensionTarget.COLLECTION_ITEM,
            collection_item=item,
            requested_date=date(2026, 3, 30),
            now=NOW,
        )

        assert (extension.days, extension.requested_date) == (7, date(2026, 3, 30))
        assert _item_due(record, item).date() == date(2026, 3, 30)

    def test_a_time_limit_extension_moves_the_time_limit(self, mock_site_context):
        record, _item = _record_with_a_dated_topic(time_limit_days=30)
        before = course_deadlines(record, now=NOW).time_limit.due_at
        assert before is not None

        extend_deadline(
            record,
            actor=UserFactory(),
            reason="Late",
            target_kind=ExtensionTarget.TIME_LIMIT,
            days=10,
            now=NOW,
        )

        assert course_deadlines(record, now=NOW).time_limit.due_at == before + (
            timedelta(days=10)
        )

    def test_a_course_extension_moves_every_unmet_deadline(self, mock_site_context):
        record, item = _record_with_a_dated_topic()
        before = _item_due(record, item)

        extend_deadline(
            record,
            actor=UserFactory(),
            reason="Late",
            target_kind=ExtensionTarget.COURSE,
            days=2,
            now=NOW,
        )

        assert _item_due(record, item) == before + timedelta(days=2)

    def test_accepts_exactly_the_maximum(self, mock_site_context):
        record, item = _record_with_a_dated_topic()

        extension = extend_deadline(
            record,
            actor=UserFactory(),
            reason="Late",
            target_kind=ExtensionTarget.COLLECTION_ITEM,
            collection_item=item,
            days=MAX_EXTENSION_DAYS,
            now=NOW,
        )

        assert extension.days == MAX_EXTENSION_DAYS

    @pytest.mark.parametrize(
        ("target_kind", "days", "requested_date", "with_item"),
        [
            pytest.param(
                "collection_item", 3, DUE + timedelta(days=3), True, id="both"
            ),
            pytest.param("collection_item", None, None, True, id="neither"),
            pytest.param(
                "course", None, DUE + timedelta(days=3), False, id="course-date"
            ),
            pytest.param("collection_item", 3, None, False, id="missing-item"),
            pytest.param("time_limit", 3, None, True, id="stray-item"),
            pytest.param("collection_item", None, DUE, True, id="date-on-deadline"),
            pytest.param(
                "collection_item", None, DUE - timedelta(days=1), True, id="date-before"
            ),
            pytest.param("collection_item", 0, None, True, id="zero-days"),
            pytest.param(
                "collection_item",
                MAX_EXTENSION_DAYS + 1,
                None,
                True,
                id="too-many-days",
            ),
            pytest.param(
                "collection_item",
                None,
                DUE + timedelta(days=MAX_EXTENSION_DAYS + 1),
                True,
                id="date-too-far",
            ),
            pytest.param("time_limit", 3, None, False, id="no-time-limit"),
        ],
    )
    def test_refuses_invalid_input_and_writes_nothing(
        self, mock_site_context, target_kind, days, requested_date, with_item
    ):
        record, item = _record_with_a_dated_topic()

        with pytest.raises(DeadlineActionError):
            extend_deadline(
                record,
                actor=UserFactory(),
                reason="Late",
                target_kind=target_kind,
                collection_item=item if with_item else None,
                days=days,
                requested_date=requested_date,
                now=NOW,
            )

        assert (
            DeadlineExtension._base_manager.count(),
            AuditLogEntry.unscoped.count(),
        ) == (
            0,
            0,
        )

    def test_refuses_an_item_with_no_deadline(self, mock_site_context):
        record, item = _record_with_a_dated_topic(due_date=None)

        with pytest.raises(DeadlineActionError):
            extend_deadline(
                record,
                actor=UserFactory(),
                reason="Late",
                target_kind=ExtensionTarget.COLLECTION_ITEM,
                collection_item=item,
                days=3,
                now=NOW,
            )

    def test_refuses_a_course_extension_with_nothing_to_move(self, mock_site_context):
        record, _item = _record_with_a_dated_topic(due_date=None)

        with pytest.raises(DeadlineActionError):
            extend_deadline(
                record,
                actor=UserFactory(),
                reason="Late",
                target_kind=ExtensionTarget.COURSE,
                days=3,
                now=NOW,
            )

    def test_refuses_a_complete_record(self, mock_site_context):
        record, item = _record_with_a_dated_topic()
        CourseProgress._base_manager.filter(pk=record.pk).update(completed_time=NOW)

        with pytest.raises(DeadlineActionError):
            extend_deadline(
                record,
                actor=UserFactory(),
                reason="Late",
                target_kind=ExtensionTarget.COLLECTION_ITEM,
                collection_item=item,
                days=3,
                now=NOW,
            )

    @pytest.mark.parametrize(
        "reason",
        ["", "   ", "x" * (REASON_LENGTH + 1)],
        ids=["blank", "whitespace", "too long"],
    )
    def test_refuses_an_unusable_reason(self, mock_site_context, reason):
        record, item = _record_with_a_dated_topic()

        with pytest.raises(DeadlineActionError):
            extend_deadline(
                record,
                actor=UserFactory(),
                reason=reason,
                target_kind=ExtensionTarget.COLLECTION_ITEM,
                collection_item=item,
                days=3,
                now=NOW,
            )

    def test_writes_one_audit_entry_with_both_instants(self, mock_site_context):
        record, item = _record_with_a_dated_topic()
        actor = UserFactory()
        due_before = _item_due(record, item)
        assert item.child is not None

        extend_deadline(
            record,
            actor=actor,
            reason="Was ill",
            target_kind=ExtensionTarget.COLLECTION_ITEM,
            collection_item=item,
            days=4,
            now=NOW,
        )

        assert_entry(
            action="deadline.extended",
            actor=actor,
            target=record.learner,
            target_label=record.learner.user.display_name,
            organisation=record.learner.organisation,
            subjects=[record.course],
            details={
                "course": record.course.title,
                "target_kind": "collection_item",
                "collection_item": item.child.title,
                "days": 4,
                "due_at_before": due_before.isoformat(),
                "due_at_after": (due_before + timedelta(days=4)).isoformat(),
            },
            reason="Was ill",
        )

    def test_a_course_extension_audits_no_instants(self, mock_site_context):
        record, _item = _record_with_a_dated_topic()

        extend_deadline(
            record,
            actor=UserFactory(),
            reason="Late",
            target_kind=ExtensionTarget.COURSE,
            days=2,
            now=NOW,
        )

        entry = AuditLogEntry.unscoped.get()
        assert (
            entry.details["collection_item"],
            entry.details["due_at_before"],
            entry.details["due_at_after"],
        ) == (None, None, None)

    def test_fires_one_webhook_after_commit(
        self, mock_site_context, django_capture_on_commit_callbacks
    ):
        record, item = _record_with_a_dated_topic()
        actor = UserFactory()
        due_before = _item_due(record, item)

        with django_capture_on_commit_callbacks(execute=True):
            extension = extend_deadline(
                record,
                actor=actor,
                reason="Was ill",
                target_kind=ExtensionTarget.COLLECTION_ITEM,
                collection_item=item,
                days=4,
                now=NOW,
            )

        (event,) = _events("deadline.extended")
        assert event.payload["extension_id"] == str(extension.pk)
        assert event.payload["target_kind"] == "collection_item"
        assert event.payload["collection_item_id"] == str(item.pk)
        assert event.payload["days"] == 4
        assert event.payload["due_at_before"] == due_before.isoformat()
        assert (
            event.payload["due_at_after"]
            == (due_before + timedelta(days=4)).isoformat()
        )
        assert event.payload["actor_id"] == str(actor.pk)
        assert event.payload["course_progress_id"] == str(record.pk)

    def test_the_webhook_does_not_fire_before_commit(self, mock_site_context):
        record, item = _record_with_a_dated_topic()

        extend_deadline(
            record,
            actor=UserFactory(),
            reason="Late",
            target_kind=ExtensionTarget.COLLECTION_ITEM,
            collection_item=item,
            days=4,
            now=NOW,
        )

        assert _events("deadline.extended") == []

    def test_notifies_the_learner_once_without_the_reason(
        self, mock_site_context, django_capture_on_commit_callbacks
    ):
        record, item = _record_with_a_dated_topic()

        with django_capture_on_commit_callbacks(execute=True):
            extend_deadline(
                record,
                actor=UserFactory(),
                reason="Private words",
                target_kind=ExtensionTarget.COLLECTION_ITEM,
                collection_item=item,
                days=4,
                now=NOW,
            )

        notification = Notification.objects.get()
        assert (notification.user, notification.category) == (
            record.learner.user,
            "deadline.extended",
        )
        assert "Private words" not in str(notification.data)
        (event,) = _events("deadline.extended")
        assert "Private words" not in str(event.payload)

    @pytest.mark.parametrize(
        ("target_kind", "days", "expected"),
        [
            pytest.param(
                "collection_item",
                4,
                ["Your educator extended the deadline for", "24 Mar 2026"],
                id="item",
            ),
            pytest.param(
                "time_limit",
                4,
                ["Your educator extended your time limit for", "9 Apr 2026"],
                id="time-limit",
            ),
            pytest.param(
                "course",
                1,
                ["Your educator moved your deadlines in", "by 1 day."],
                id="course",
            ),
        ],
    )
    def test_the_summary_follows_the_target_kind(
        self,
        mock_site_context,
        django_capture_on_commit_callbacks,
        target_kind,
        days,
        expected,
    ):
        record, item = _record_with_a_dated_topic(time_limit_days=26)

        with django_capture_on_commit_callbacks(execute=True):
            extend_deadline(
                record,
                actor=UserFactory(),
                reason="Late",
                target_kind=target_kind,
                collection_item=item if target_kind == "collection_item" else None,
                days=days,
                now=NOW,
            )

        summary = Notification.objects.get().data["summary"]
        assert all(part in summary for part in expected)
        assert record.course.title in summary

    def test_the_learner_acting_gets_no_notification_but_the_webhook_fires(
        self, mock_site_context, django_capture_on_commit_callbacks
    ):
        record, item = _record_with_a_dated_topic()

        with django_capture_on_commit_callbacks(execute=True):
            extend_deadline(
                record,
                actor=record.learner.user,
                reason="Late",
                target_kind=ExtensionTarget.COLLECTION_ITEM,
                collection_item=item,
                days=4,
                now=NOW,
            )

        assert Notification.objects.count() == 0
        assert len(_events("deadline.extended")) == 1

    def test_a_rolled_back_extension_writes_and_fires_nothing(
        self, mock_site_context, django_capture_on_commit_callbacks
    ):
        record, item = _record_with_a_dated_topic()

        with (
            django_capture_on_commit_callbacks(execute=True),
            pytest.raises(RuntimeError),
        ):
            _then_roll_back(
                lambda: extend_deadline(
                    record,
                    actor=UserFactory(),
                    reason="Late",
                    target_kind=ExtensionTarget.COLLECTION_ITEM,
                    collection_item=item,
                    days=4,
                    now=NOW,
                )
            )

        assert (
            DeadlineExtension._base_manager.count(),
            AuditLogEntry.unscoped.count(),
            Notification.objects.count(),
            len(_events("deadline.extended")),
        ) == (0, 0, 0, 0)

    def test_extending_is_allowed_while_paused(self, mock_site_context):
        record, item = _record_with_a_dated_topic()
        CoursePauseFactory(course_progress=record, started_at=NOW - timedelta(days=1))

        extension = extend_deadline(
            record,
            actor=UserFactory(),
            reason="Late",
            target_kind=ExtensionTarget.COLLECTION_ITEM,
            collection_item=item,
            days=4,
            now=NOW,
        )

        assert extension.pk is not None
