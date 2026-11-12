"""The services that change a learner's deadlines: one transaction, one audit entry, one
webhook after commit and one notification for the learner. They run with no request (the
housekeeping sweep and seed commands call them), so they read through `_base_manager` and
set `site` by hand."""

from __future__ import annotations

from datetime import date, datetime

from django.db import transaction
from django.utils import formats, timezone
from django.utils.translation import gettext as _
from django.utils.translation import ngettext

from freedom_ls.accounts.models import User
from freedom_ls.audit_log.models import REASON_LENGTH
from freedom_ls.base.date_display import DATE_DISPLAY_FORMAT
from freedom_ls.comms.notify import raise_notification
from freedom_ls.content_engine.models import ContentCollectionItem
from freedom_ls.deadlines.models import (
    MAX_EXTENSION_DAYS,
    CoursePause,
    DeadlineExtension,
    ExtensionTarget,
)
from freedom_ls.deadlines.queries import open_pause
from freedom_ls.deadlines.resolver import (
    CourseDeadlines,
    ResolvedDeadline,
    course_deadlines,
)
from freedom_ls.learner_management.learner_actions import record_learner_entry
from freedom_ls.learner_management.utils import (
    fire_webhook_event_on_commit,
    learner_webhook_payload,
)
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.learner_progress.queries import completed_collection_item_ids
from freedom_ls.site_aware_models.time_zones import site_time_zone


class DeadlineActionError(ValueError):
    """Input a staff member can correct; the admin shows its message on the form."""


def _locked(record: CourseProgress) -> CourseProgress:
    # Lock the record alone: the join also reads the course, learner and site rows, which
    # unrelated actions and content loads touch.
    return (
        CourseProgress._base_manager.select_for_update(of=("self",))
        .select_related("learner__user", "learner__organisation", "course", "site")
        .get(pk=record.pk)
    )


def _check(record: CourseProgress, reason: str) -> str:
    """Return the reason as it is stored, so the row and the audit entry cannot differ."""
    reason = reason.strip()
    if not reason:
        raise DeadlineActionError(_("Give a reason."))
    if len(reason) > REASON_LENGTH:
        raise DeadlineActionError(
            _("Keep the reason to %(limit)d characters or fewer.")
            % {"limit": REASON_LENGTH}
        )
    if record.completed_time is not None:
        raise DeadlineActionError(_("This course is complete."))
    return reason


def _notify(
    record: CourseProgress, actor: User | None, category: str, data: dict[str, str]
) -> None:
    # The person who acted already knows; everyone else was not there.
    if actor is not None and actor.pk == record.learner.user_id:
        return
    raise_notification(
        user=record.learner.user,
        category=category,
        target=record.course,
        site_id=record.site_id,
        data=data,
    )


def _days_text(days: int) -> str:
    return ngettext("%(count)d day", "%(count)d days", days) % {"count": days}


def _course_payload(record: CourseProgress) -> dict[str, object]:
    return {
        **learner_webhook_payload(record.learner),
        "course_id": str(record.course_id),
        "course_title": record.course.title,
        "course_progress_id": str(record.pk),
    }


def pause_course(
    record: CourseProgress,
    *,
    actor: User | None,
    reason: str,
    planned_resume_on: date | None = None,
    now: datetime | None = None,
) -> CoursePause:
    """Stop the record's clock. A pause whose planned resume has passed but was never
    written is closed and announced first, so "resumed" is heard before "paused"."""
    now = now or timezone.now()
    with transaction.atomic():
        locked = _locked(record)
        reason = _check(locked, reason)
        tz = site_time_zone(locked.site)
        if (
            planned_resume_on is not None
            and planned_resume_on <= now.astimezone(tz).date()
        ):
            raise DeadlineActionError(_("Pick a resume date after today."))
        unended = CoursePause._base_manager.filter(
            course_progress=locked, ended_at__isnull=True
        ).first()
        if unended is not None:
            if unended.is_open(now, tz):
                raise DeadlineActionError(_("This course is already paused."))
            _announce_planned_resume(unended, locked, now)
        pause = CoursePause._base_manager.create(
            site=locked.site,
            course_progress=locked,
            started_at=now,
            planned_resume_on=planned_resume_on,
            reason=reason,
            started_by=actor,
        )
        planned_at = pause.planned_resume_instant(tz)
        record_learner_entry(
            locked.learner,
            "course.paused",
            actor,
            reason=reason,
            subjects=[locked.course],
            details={
                "course": locked.course.title,
                "planned_resume_on": (
                    planned_resume_on.isoformat() if planned_resume_on else None
                ),
            },
        )
        fire_webhook_event_on_commit(
            "course.paused",
            {
                **_course_payload(locked),
                "pause_id": str(pause.pk),
                "paused_at": now.isoformat(),
                "planned_resume_at": planned_at.isoformat() if planned_at else None,
                "actor_id": str(actor.pk) if actor else None,
            },
            locked.site,
        )
        if planned_resume_on is not None:
            resume_text = _("It resumes on %(date)s.") % {
                "date": formats.date_format(planned_resume_on, DATE_DISPLAY_FORMAT)
            }
        else:
            resume_text = _("You can continue when they resume it.")
        _notify(
            locked,
            actor,
            "course.paused",
            {"course_title": locked.course.title, "resume_text": resume_text},
        )
    return pause


def resume_course(
    record: CourseProgress,
    *,
    actor: User | None,
    reason: str,
    now: datetime | None = None,
) -> CoursePause | None:
    """End the record's open pause, moving its deadlines by the days paused. None, writing
    nothing, when the record is not paused, so a repeated post is a no-op.

    Setting `resume_announced_at` here keeps the sweep from announcing a pause staff
    already ended."""
    now = now or timezone.now()
    with transaction.atomic():
        locked = _locked(record)
        pause = open_pause(locked, now)
        if pause is None:
            return None
        reason = _check(locked, reason)
        pause.ended_at = now
        pause.ended_by = actor
        pause.ended_reason = reason
        pause.resume_announced_at = now
        pause.save()
        _record_resumed(
            pause,
            locked,
            actor=actor,
            resumed_at=now,
            now=now,
            planned=False,
            reason=reason,
        )
    return pause


def announce_planned_resume(pause: CoursePause, *, now: datetime | None = None) -> bool:
    """Close a pause whose planned resume has passed and announce it once, with no actor.
    False when it is not yet due or another caller already announced it."""
    now = now or timezone.now()
    with transaction.atomic():
        locked = _locked(pause.course_progress)
        return _announce_planned_resume(pause, locked, now)


def _announce_planned_resume(
    pause: CoursePause, locked: CourseProgress, now: datetime
) -> bool:
    """Close a pause whose planned resume has passed and announce it once, with no actor.
    The caller holds the record's lock. False when the planned instant is not yet reached
    or another caller already announced it."""
    planned = pause.planned_resume_instant(site_time_zone(locked.site))
    if planned is None or planned > now:
        return False
    # A conditional update is the claim: of two callers, one row count is 1.
    claimed = CoursePause._base_manager.filter(
        pk=pause.pk, resume_announced_at__isnull=True
    ).update(resume_announced_at=now)
    CoursePause._base_manager.filter(pk=pause.pk, ended_at__isnull=True).update(
        ended_at=planned
    )
    if not claimed:
        return False
    pause.ended_at = pause.ended_at or planned
    pause.resume_announced_at = now
    _record_resumed(
        pause, locked, actor=None, resumed_at=planned, now=now, planned=True
    )
    return True


def _record_resumed(
    pause: CoursePause,
    locked: CourseProgress,
    *,
    actor: User | None,
    resumed_at: datetime,
    now: datetime,
    planned: bool,
    reason: str = "",
) -> None:
    """The audit entry, webhook and notification for a pause that has ended."""
    tz = site_time_zone(locked.site)
    shift_days = pause.paused_days(now, tz)
    planned_at = pause.planned_resume_instant(tz)
    title = locked.course.title
    record_learner_entry(
        locked.learner,
        "course.resumed",
        actor,
        reason=reason,
        subjects=[locked.course],
        details={"course": title, "shift_days": shift_days},
    )
    fire_webhook_event_on_commit(
        "course.resumed",
        {
            **_course_payload(locked),
            "pause_id": str(pause.pk),
            "paused_at": pause.started_at.isoformat(),
            "planned_resume_at": planned_at.isoformat() if planned_at else None,
            "actor_id": str(actor.pk) if actor else None,
            "resumed_at": resumed_at.isoformat(),
            "shift_days": shift_days,
            "planned": planned,
        },
        locked.site,
    )
    values = {"course_title": title, "days": _days_text(shift_days)}
    if planned:
        summary = _("%(course_title)s has resumed. Your deadlines moved by %(days)s.")
    else:
        summary = _(
            "Your educator resumed %(course_title)s. Your deadlines moved by %(days)s."
        )
    _notify(locked, actor, "course.resumed", {"summary": summary % values})


def extend_deadline(
    record: CourseProgress,
    *,
    actor: User | None,
    reason: str,
    target_kind: str,
    collection_item: ContentCollectionItem | None = None,
    days: int | None = None,
    requested_date: date | None = None,
    now: datetime | None = None,
) -> DeadlineExtension:
    """Add days to one deadline, the course time limit or every unmet deadline of the
    record, given as a number of days or as the date the target should fall on. Allowed
    while paused and after access ended: a time-limit extension that lifts the access end
    past `now` restores access."""
    now = now or timezone.now()
    with transaction.atomic():
        locked = _locked(record)
        reason = _check(locked, reason)
        if (days is None) == (requested_date is None):
            raise DeadlineActionError(_("Give either days or a date."))
        if target_kind == ExtensionTarget.COURSE and requested_date is not None:
            raise DeadlineActionError(_("Whole course takes days, not a date."))
        if (target_kind == ExtensionTarget.COLLECTION_ITEM) != (
            collection_item is not None
        ):
            raise DeadlineActionError(_("Pick an item."))
        before = course_deadlines(locked, now=now)
        target = _extension_target(locked, before, target_kind, collection_item)
        if requested_date is not None and target is not None and target.due_at:
            days = (requested_date - target.due_at.astimezone(before.zone).date()).days
            if days < 1:
                raise DeadlineActionError(_("Pick a date after the current deadline."))
        if days is None or not 1 <= days <= MAX_EXTENSION_DAYS:
            raise DeadlineActionError(
                _("Give between 1 and %(max)d days.") % {"max": MAX_EXTENSION_DAYS}
            )
        extension = DeadlineExtension._base_manager.create(
            site=locked.site,
            course_progress=locked,
            target_kind=target_kind,
            collection_item=collection_item,
            days=days,
            requested_date=requested_date,
            reason=reason,
            set_by=actor,
        )
        after = course_deadlines(locked, now=now)
        due_before: datetime | None = None
        due_after: datetime | None = None
        if target_kind == ExtensionTarget.COLLECTION_ITEM and collection_item:
            due_before = before.items[collection_item.pk].due_at
            due_after = after.items[collection_item.pk].due_at
        elif target_kind == ExtensionTarget.TIME_LIMIT:
            due_before = before.time_limit.due_at
            due_after = after.time_limit.due_at
        item_child = collection_item.child if collection_item else None
        item_title = item_child.title if item_child else None
        record_learner_entry(
            locked.learner,
            "deadline.extended",
            actor,
            reason=reason,
            subjects=[locked.course],
            details={
                "course": locked.course.title,
                "target_kind": target_kind,
                "collection_item": item_title,
                "days": days,
                "due_at_before": due_before.isoformat() if due_before else None,
                "due_at_after": due_after.isoformat() if due_after else None,
            },
        )
        fire_webhook_event_on_commit(
            "deadline.extended",
            {
                **_course_payload(locked),
                "extension_id": str(extension.pk),
                "target_kind": target_kind,
                "collection_item_id": (
                    str(collection_item.pk) if collection_item else None
                ),
                "days": days,
                "due_at_before": due_before.isoformat() if due_before else None,
                "due_at_after": due_after.isoformat() if due_after else None,
                "actor_id": str(actor.pk) if actor else None,
            },
            locked.site,
        )
        values = {
            "item": item_title,
            "course": locked.course.title,
            "days": _days_text(days),
            "date": (
                formats.date_format(
                    due_after.astimezone(after.zone).date(), DATE_DISPLAY_FORMAT
                )
                if due_after
                else ""
            ),
        }
        if target_kind == ExtensionTarget.COLLECTION_ITEM:
            summary = _(
                "Your educator extended the deadline for %(item)s in %(course)s "
                "to %(date)s."
            )
        elif target_kind == ExtensionTarget.TIME_LIMIT:
            summary = _(
                "Your educator extended your time limit for %(course)s to %(date)s."
            )
        else:
            summary = _("Your educator moved your deadlines in %(course)s by %(days)s.")
        _notify(locked, actor, "deadline.extended", {"summary": summary % values})
    return extension


def _extension_target(
    record: CourseProgress,
    deadlines: CourseDeadlines,
    target_kind: str,
    collection_item: ContentCollectionItem | None,
) -> ResolvedDeadline | None:
    """The deadline an extension moves, refusing a target that has none. None for the
    whole course, which has no single deadline to read a date from."""
    if target_kind == ExtensionTarget.COLLECTION_ITEM and collection_item:
        item = deadlines.items.get(collection_item.pk)
        if item is None or item.due_at is None:
            raise DeadlineActionError(_("This item has no deadline"))
        return item
    if target_kind == ExtensionTarget.TIME_LIMIT:
        if deadlines.time_limit.due_at is None:
            raise DeadlineActionError(_("This course has no time limit"))
        return deadlines.time_limit
    if target_kind != ExtensionTarget.COURSE:
        raise DeadlineActionError(_("Pick what to extend."))
    done = completed_collection_item_ids(record)
    has_unmet = any(
        resolved.due_at is not None and item_id not in done
        for item_id, resolved in deadlines.items.items()
    )
    if deadlines.time_limit.due_at is None and not has_unmet:
        raise DeadlineActionError(_("This course has no deadlines to move."))
    return None
