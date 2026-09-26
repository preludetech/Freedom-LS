"""Seed exact QA data for the notifications feature (bell, panel, centre).

Destructive and idempotent: every run first deletes the four personas and the
QA Notify courses, then rebuilds them, so the notification state is exact.

PERSONAS (login-ready: verified+primary EmailAddress, password == email):
  notify.learner@demodev.example.com   Learner A, exactly 26 notifications:
      3 unseen+unread (now, -12 min, -40 min)
      2 seen+unread (yesterday 10:15 and 14:30, site time zone)
      21 read, spread over six weeks. Among them one whose target course has
      been deleted (3 days ago, page 1) and one 'legacy.unregistered' (not in
      the registry, so hidden by Notification.objects -> 25 visible).
  notify.other@demodev.example.com     Learner B, 2 unseen notifications; has a
      Learner profile on the default organisation but no course registrations.
  notify.educator@demodev.example.com  organisation_staff on the default
      organisation (reaches /educator/), 1 unseen notification.
  notify.many@demodev.example.com      Learner C, 120 unseen notifications.

COURSES (free, published, one markdown topic each):
  QA Notify Open        Learner A NOT registered, no notification.
  QA Notify Finish      Learner A registered (active), not finished, no notification.
  QA Notify Reactivate  Learner A registration is_active=False, no notification.
  QA Notify History 1-3 targets for the historical notifications (A registered).

Registration signals raise 'course.registered' on commit; every such row is
deleted before the historical notifications are written.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import cast

import djclick as click
from allauth.account.models import EmailAddress

from django.conf import settings
from django.contrib.sites.models import Site
from django.http import HttpRequest
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.comms.factories import NotificationFactory
from freedom_ls.comms.models import Notification
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import Course, CourseVisibility, Topic
from freedom_ls.learner_management.factories import LearnerCourseRegistrationFactory
from freedom_ls.learner_management.models import LearnerCourseRegistration
from freedom_ls.learner_management.utils import ensure_learner
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.organisations.utils import get_default_organisation
from freedom_ls.role_based_permissions.utils import assign_object_role
from freedom_ls.site_aware_models.models import _thread_locals

LEARNER_A = "notify.learner@demodev.example.com"
LEARNER_B = "notify.other@demodev.example.com"
EDUCATOR = "notify.educator@demodev.example.com"
LEARNER_C = "notify.many@demodev.example.com"

OPEN_TITLE = "QA Notify Open"
FINISH_TITLE = "QA Notify Finish"
REACTIVATE_TITLE = "QA Notify Reactivate"
DELETED_TITLE = "QA Notify Deleted Course"
HISTORY_TITLES = ["QA Notify History 1", "QA Notify History 2", "QA Notify History 3"]

# Days ago for Learner A's 21 read notifications; index 2 is the deleted-course
# one (3 days ago, inside page 1), index 16 the unregistered-category one.
READ_DAYS_AGO = [
    2,
    2,
    3,
    3,
    5,
    5,
    7,
    9,
    9,
    12,
    14,
    16,
    19,
    21,
    21,
    24,
    28,
    31,
    35,
    38,
    41,
]
DELETED_INDEX = 2
LEGACY_INDEX = 16


class _SiteContextRequest(HttpRequest):
    _cached_site: Site


@contextmanager
def _site_context(site: Site) -> Iterator[None]:
    """Publish ``site`` on the thread local, as CurrentSiteMiddleware (and the
    tests' mock_site_context fixture) does, so site-aware saves and
    assign_object_role resolve the right site."""
    settings.SITE_ID = site.pk
    Site.objects.clear_cache()
    request = _SiteContextRequest()
    request._cached_site = site
    had_request = hasattr(_thread_locals, "request")
    previous = getattr(_thread_locals, "request", None)
    _thread_locals.request = request
    try:
        yield
    finally:
        if had_request:
            _thread_locals.request = previous
        else:
            delattr(_thread_locals, "request")


def _teardown(site: Site) -> None:
    emails = [LEARNER_A, LEARNER_B, EDUCATOR, LEARNER_C]
    users = User.objects.filter(email__in=emails)
    # CourseProgress PROTECTs Learner, which PROTECTs User; clear the personas' own
    # progress records (minted by the registration signal) first.
    progress = CourseProgress._base_manager.filter(learner__user__email__in=emails)
    if progress.exists():
        click.echo(f"Deleting {progress.count()} CourseProgress row(s) for personas")
        click.echo(f"  cascade: {progress.delete()}")
    for user in users:
        click.echo(f"Deleting user pk={user.pk} {user}")
    if users.exists():
        click.echo(f"  cascade: {users.delete()}")
    titles = [
        OPEN_TITLE,
        FINISH_TITLE,
        REACTIVATE_TITLE,
        DELETED_TITLE,
        *HISTORY_TITLES,
    ]
    courses = Course._base_manager.filter(site=site, title__in=titles)
    for course in courses:
        click.echo(f"Deleting course pk={course.pk} {course.slug}")
    if courses.exists():
        click.echo(f"  cascade: {courses.delete()}")
    # Topics outlive their course (only the ContentCollectionItem cascades).
    topics = Topic._base_manager.filter(
        site=site, title__in=[f"{title} - Welcome" for title in titles]
    )
    if topics.exists():
        click.echo(f"Deleting {topics.count()} QA Notify topic(s)")
        click.echo(f"  cascade: {topics.delete()}")


def _user(site: Site, email: str, first_name: str, last_name: str) -> User:
    user = cast(
        User,
        UserFactory(
            email=email,
            first_name=first_name,
            last_name=last_name,
            is_active=True,
            password=email,
            site=site,
        ),
    )
    EmailAddress.objects.update_or_create(
        user=user, email=user.email, defaults={"verified": True, "primary": True}
    )
    return user


def _course(site: Site, title: str) -> Course:
    course = cast(
        Course,
        CourseFactory(
            title=title,
            visibility=CourseVisibility.PUBLISHED,
            access_config={"access_type": "free"},
            site=site,
        ),
    )
    topic = TopicFactory(
        title=f"{title} - Welcome",
        content=f"# Welcome to {title}\n\nA short topic for notification QA.",
        site=site,
    )
    ContentCollectionItemFactory(
        collection_object=course, child_object=topic, site=site
    )
    return course


def _notify(
    site: Site,
    user: User,
    course: Course,
    created_at: datetime,
    *,
    category: str = "course.registered",
    seen_at: datetime | None = None,
    read_at: datetime | None = None,
) -> Notification:
    notification = cast(
        Notification,
        NotificationFactory(
            site=site,
            user=user,
            category=category,
            target=course,
            data={"course_title": course.title},
            seen_at=seen_at,
            read_at=read_at,
        ),
    )
    # created_at is auto_now_add; backdate it with an update.
    Notification._base_manager.filter(pk=notification.pk).update(created_at=created_at)
    return notification


def _seed(site: Site) -> None:
    now = timezone.now()
    organisation = get_default_organisation(site)

    learner_a = _user(site, LEARNER_A, "Notify", "Learner")
    learner_b = _user(site, LEARNER_B, "Notify", "Other")
    educator = _user(site, EDUCATOR, "Notify", "Educator")
    learner_c = _user(site, LEARNER_C, "Notify", "Many")
    assign_object_role(educator, organisation, "organisation_staff")

    open_course = _course(site, OPEN_TITLE)
    finish_course = _course(site, FINISH_TITLE)
    reactivate_course = _course(site, REACTIVATE_TITLE)
    history = [_course(site, title) for title in HISTORY_TITLES]

    learner = ensure_learner(learner_a, organisation)
    # Learner B gets a Learner profile (no registrations) so the admin's
    # LearnerCourseRegistration "learner" autocomplete can find them.
    ensure_learner(learner_b, organisation)
    for course in [finish_course, *history]:
        LearnerCourseRegistrationFactory(
            site=site, learner=learner, course=course, is_active=True
        )
    reactivate_reg = cast(
        LearnerCourseRegistration,
        LearnerCourseRegistrationFactory(
            site=site, learner=learner, course=reactivate_course, is_active=False
        ),
    )

    # Registration signals raise on_commit; remove everything raised during setup.
    raised = Notification._base_manager.filter(
        user__in=[learner_a, learner_b, educator, learner_c]
    )
    click.echo(f"Removing {raised.count()} notification(s) raised by setup signals")
    raised.delete()

    # Learner A: 3 unseen+unread.
    for minutes in (0, 12, 40):
        _notify(site, learner_a, history[minutes % 3], now - timedelta(minutes=minutes))

    # Learner A: 2 seen+unread from yesterday.
    yesterday = timezone.localtime(now).date() - timedelta(days=1)
    for hour, minute in ((10, 15), (14, 30)):
        created = datetime(
            yesterday.year,
            yesterday.month,
            yesterday.day,
            hour,
            minute,
            tzinfo=timezone.get_current_timezone(),
        )
        _notify(
            site,
            learner_a,
            history[hour % 3],
            created,
            seen_at=created + timedelta(hours=1),
        )

    # Learner A: 21 read.
    deleted_course = _course(site, DELETED_TITLE)
    deleted_notification_id = None
    for index, days in enumerate(READ_DAYS_AGO):
        created = now - timedelta(days=days, hours=index % 5, minutes=7 * index)
        seen = created + timedelta(minutes=30)
        read = created + timedelta(hours=2)
        category = "course.registered"
        course = history[index % 3]
        if index == DELETED_INDEX:
            course = deleted_course
        if index == LEGACY_INDEX:
            category = "legacy.unregistered"
        notification = _notify(
            site,
            learner_a,
            course,
            created,
            category=category,
            seen_at=seen,
            read_at=read,
        )
        if index == DELETED_INDEX:
            deleted_notification_id = notification.pk

    click.echo(f"Deleting course pk={deleted_course.pk} ({deleted_course.slug})")
    click.echo(f"  cascade: {deleted_course.delete()}")

    # Learner B: 2 unseen.
    b_ids = [
        _notify(site, learner_b, history[i], now - timedelta(minutes=5 + 20 * i)).pk
        for i in range(2)
    ]
    # Educator: 1 unseen.
    _notify(site, educator, history[0], now - timedelta(minutes=3))
    # Learner C: 120 unseen.
    for i in range(120):
        _notify(
            site,
            learner_c,
            history[i % 3],
            now - timedelta(minutes=30 * i),
        )

    click.echo("\n=== Summary ===")
    click.echo(f"Site: {site.name} (id={site.pk}, domain={site.domain})")
    for course in [open_course, finish_course, reactivate_course, *history]:
        click.echo(f"Course: {course.title} -> /courses/{course.slug}/access/")
    click.echo(f"Reactivate registration UUID: {reactivate_reg.pk}")
    click.echo(f"Deleted-course notification UUID: {deleted_notification_id}")
    click.echo(f"Learner B notification UUIDs: {', '.join(str(i) for i in b_ids)}")
    for user in [learner_a, learner_b, educator, learner_c]:
        base = Notification._base_manager.filter(user=user)
        click.echo(
            f"{user.email}: total={base.count()} "
            f"visible={Notification.objects.for_user(user).count()} "
            f"unseen={Notification.objects.for_user(user).unseen().count()} "
            f"unread={Notification.objects.for_user(user).unread().count()}"
        )
    click.echo("Passwords: each user's own email address.")


@click.command()
@click.option("--site-name", default="DemoDev", show_default=True)
def command(site_name: str) -> None:
    """Delete and rebuild the notifications QA personas and courses."""
    site = Site.objects.get(name=site_name)
    with _site_context(site):
        _teardown(site)
        _seed(site)
