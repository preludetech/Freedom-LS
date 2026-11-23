# ruff: noqa: T201, S101 -- a manage.py shell script whose output is printed for the QA operator
"""Learner C (qa-revision-back@) on qa-revision-course: nothing due, every bank question scheduled +10 days.

Run: uv run python manage.py shell < this_file
Set DRY = True below to inspect only.
"""

from datetime import timedelta

from django.contrib.sites.models import Site
from django.utils import timezone

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import Course
from freedom_ls.learner_interface.views import _due_count, _revision_due_badge
from freedom_ls.learner_management.queries import learner_for_course
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.revision.factories import RevisionScheduleFactory
from freedom_ls.revision.models import RevisionSchedule
from freedom_ls.revision.queries import bank_questions

DRY = True
EMAIL = "qa-revision-back@example.com"
SLUG = "qa-revision-course"
site = Site.objects.get(pk=2)
user = User._base_manager.get(email=EMAIL, site=site)
course = Course._base_manager.get(slug=SLUG, site=site)
print(
    "user",
    user.pk,
    user,
    "site",
    user.site_id,
    "| course",
    course.pk,
    course,
    "site",
    course.site_id,
)
resolved = learner_for_course(user, course)
assert resolved is not None, "learner not registered"
record = CourseProgress._base_manager.get(learner=resolved.learner, course=course)
print("record", record.pk, record)

now = timezone.now()
bank = list(bank_questions(record).order_by("pk"))
bank_ids = {q.pk for q in bank}
print(
    "bank size",
    len(bank),
    "| ready before",
    _due_count(user, record, now),
    "| badge before",
    repr(_revision_due_badge(user, record, now)),
)
existing = list(RevisionSchedule._base_manager.filter(user=user).order_by("due"))
print("existing schedules for user:", len(existing))
for s in existing:
    print(
        "  ",
        s.pk,
        "site",
        s.site_id,
        "q",
        s.question_id,
        "due",
        s.due.isoformat(),
        "in bank" if s.question_id in bank_ids else "NOT in this bank",
    )
scheduled_ids = {s.question_id for s in existing}
missing = [q for q in bank if q.pk not in scheduled_ids]
print("bank questions without schedule:", len(missing))

target = now + timedelta(days=10)
if not DRY:
    updated = RevisionSchedule._base_manager.filter(user=user).update(due=target)
    print("updated due on", updated, "rows ->", target.isoformat())
    for q in missing:
        RevisionScheduleFactory(
            user=user, question=q, due=target, last_review=now, site=site
        )
    print("created", len(missing), "schedules")
    now2 = timezone.now()
    print(
        "AFTER: schedules",
        RevisionSchedule._base_manager.filter(user=user).count(),
        "| due<=now",
        RevisionSchedule._base_manager.filter(user=user, due__lte=now2).count(),
        "| bank",
        bank_questions(record).count(),
        "| bank unscheduled",
        bank_questions(record).exclude(revision_schedules__user=user).count(),
        "| _due_count",
        _due_count(user, record, now2),
        "| badge",
        repr(_revision_due_badge(user, record, now2)),
    )
