"""Seed the learner-interface deadlines QA scenario: an outline with every deadline tier,
plus dashboard cards with deadlines.

Builds, on the named site (default DemoDev), for an existing learner (default
``demodev@email.com``), with every date counted from today in the site zone:

* a ``SiteTimeZoneConfig`` (``Africa/Johannesburg``) when the site has none;
* ``Deadline Outline Course`` with a ``CourseDeadlineConfig`` of mark_overdue on,
  close_items on and a seven-day grace window. Its outline, in player order:

  1. "Course Welcome": due six days ago, completed;
  2. "Reflection Due Today": due today at 23:59, open (TODAY);
  3. "Week One Check-in": due two days ago, started (MISSED, inside its grace window);
  4. part "Part 2: Project Work" holding "Project Plan" (due in 17 days) and a long-titled
     item (due in 22 days), both UPCOMING;
  5. "Orientation Survey": due 14 days ago, started (CLOSED, past its grace window);

* ``Deadline Upcoming Course``: first item completed, second due in ten days (UPCOMING);
* ``Deadline Partner Course``, registered through a Learner in a non-default organisation
  so its dashboard card carries the organisation byline: first item completed, second due
  two days ago (MISSED; the settings defaults mark overdue items and close none).

Deadlines live on the content rows (``ContentCollectionItem.due_*``), so the courses are
built here, not loaded from ``demo_content``, and ``content_save`` leaves them alone.

Idempotent: re-running refreshes the content, the due dates, the config and the progress
rows this command owns. It deletes nothing, so progress the tester adds on other items
stays; clear it with ``qa_reset_learner_progress --learner <email> --course-slug <slug>
--include-topics``.

Usage:
    uv run python manage.py qa_create_deadline_outline_scenario [SITE_NAME]
        [--learner-email demodev@email.com] [--organisation "Harbour College"]
"""

from dataclasses import dataclass
from datetime import date, time, timedelta
from typing import cast
from zoneinfo import ZoneInfo

import djclick as click

from django.contrib.contenttypes.models import ContentType as DjangoContentType
from django.contrib.sites.models import Site
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    CoursePartFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import (
    ContentCollectionItem,
    Course,
    CoursePart,
    CourseVisibility,
    Topic,
)
from freedom_ls.deadlines.factories import CourseDeadlineConfigFactory
from freedom_ls.deadlines.models import CourseDeadlineConfig, DeadlineSwitch
from freedom_ls.learner_management.factories import (
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import Learner, LearnerCourseRegistration
from freedom_ls.learner_progress.factories import CourseProgressFactory
from freedom_ls.learner_progress.models import CourseProgress, TopicProgress
from freedom_ls.organisations.models import Organisation
from freedom_ls.organisations.utils import get_default_organisation
from freedom_ls.site_aware_models.factories import SiteTimeZoneConfigFactory
from freedom_ls.site_aware_models.models import SiteTimeZoneConfig
from freedom_ls.site_aware_models.time_zones import site_time_zone

DEFAULT_TIME_ZONE = "Africa/Johannesburg"
GRACE_WINDOW = timedelta(days=7)
END_OF_DAY = time(23, 59)

COMPLETE = "complete"
STARTED = "started"
UNTOUCHED = "untouched"


@dataclass(frozen=True)
class TopicSpec:
    slug: str
    title: str
    due_in_days: int | None
    due_time: time | None
    progress: str
    expected: str  # the state the outline should show, for the report


@dataclass(frozen=True)
class PartSpec:
    slug: str
    title: str
    children: tuple[TopicSpec, ...]


@dataclass(frozen=True)
class CourseSpec:
    slug: str
    title: str
    items: tuple[TopicSpec | PartSpec, ...]
    in_default_organisation: bool


OUTLINE_COURSE = CourseSpec(
    slug="deadline-outline-course",
    title="Deadline Outline Course",
    in_default_organisation=True,
    items=(
        TopicSpec(
            "dl-outline-course-welcome",
            "Course Welcome",
            -6,
            None,
            COMPLETE,
            "COMPLETE (completed, had a deadline)",
        ),
        TopicSpec(
            "dl-outline-reflection-due-today",
            "Reflection Due Today",
            0,
            END_OF_DAY,
            UNTOUCHED,
            "TODAY (ready, due 23:59 site time)",
        ),
        TopicSpec(
            "dl-outline-week-one-check-in",
            "Week One Check-in",
            -2,
            None,
            STARTED,
            "MISSED (started, inside its 7-day grace window)",
        ),
        PartSpec(
            "dl-outline-part-2",
            "Part 2: Project Work",
            (
                TopicSpec(
                    "dl-outline-project-plan",
                    "Project Plan",
                    17,
                    None,
                    UNTOUCHED,
                    "UPCOMING (locked by sequential unlock)",
                ),
                TopicSpec(
                    "dl-outline-long-reflection",
                    "Writing a Detailed Reflection on Everything You Learned in the "
                    "Project",
                    22,
                    None,
                    UNTOUCHED,
                    "UPCOMING, long title (locked by sequential unlock)",
                ),
            ),
        ),
        TopicSpec(
            "dl-outline-orientation-survey",
            "Orientation Survey",
            -14,
            None,
            STARTED,
            "CLOSED (started, past its 7-day grace window)",
        ),
    ),
)

UPCOMING_COURSE = CourseSpec(
    slug="deadline-upcoming-course",
    title="Deadline Upcoming Course",
    in_default_organisation=True,
    items=(
        TopicSpec(
            "dl-upcoming-getting-started",
            "Getting Started",
            None,
            None,
            COMPLETE,
            "COMPLETE (no deadline)",
        ),
        TopicSpec(
            "dl-upcoming-first-assignment",
            "First Assignment",
            10,
            None,
            UNTOUCHED,
            "UPCOMING (ready)",
        ),
    ),
)

PARTNER_COURSE = CourseSpec(
    slug="deadline-partner-course",
    title="Deadline Partner Course",
    in_default_organisation=False,
    items=(
        TopicSpec(
            "dl-partner-introduction",
            "Introduction",
            None,
            None,
            COMPLETE,
            "COMPLETE (no deadline)",
        ),
        TopicSpec(
            "dl-partner-safety-briefing",
            "Safety Briefing",
            -2,
            None,
            UNTOUCHED,
            "MISSED (ready; default policy marks overdue, closes nothing)",
        ),
    ),
)


def _get_site(site_name: str) -> Site:
    try:
        return Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        available = list(Site.objects.values_list("name", flat=True))
        raise click.ClickException(
            f"Site '{site_name}' not found. Available: {available}"
        ) from e


def _ensure_time_zone(site: Site) -> ZoneInfo:
    """The site zone, set to Africa/Johannesburg first when the site has no zone row."""
    if not SiteTimeZoneConfig._base_manager.filter(site=site).exists():
        SiteTimeZoneConfigFactory(
            site=site, time_zone=DEFAULT_TIME_ZONE, show_time_zone_to_learners=False
        )
        click.echo(f"Site time zone set to {DEFAULT_TIME_ZONE}.")
    return site_time_zone(site)


def _course(site: Site, spec: CourseSpec) -> Course:
    course = Course._base_manager.filter(site=site, slug=spec.slug).first()
    if course is None:
        return cast(
            Course,
            CourseFactory(
                site=site,
                slug=spec.slug,
                title=spec.title,
                description=f"QA course for deadline display: {spec.title}.",
                content=f"## {spec.title}\n\nA QA course for the deadline display.\n",
                visibility=CourseVisibility.PUBLISHED,
                access_config={"access_type": "free"},
            ),
        )
    course.title = spec.title
    course.visibility = CourseVisibility.PUBLISHED
    course.access_config = {"access_type": "free"}
    course.save(update_fields=["title", "visibility", "access_config"])
    return course


def _topic(site: Site, spec: TopicSpec) -> Topic:
    topic = Topic._base_manager.filter(site=site, slug=spec.slug).first()
    content = f"# {spec.title}\n\nQA topic. Expected outline state: {spec.expected}.\n"
    if topic is None:
        return cast(
            Topic,
            TopicFactory(site=site, slug=spec.slug, title=spec.title, content=content),
        )
    topic.title = spec.title
    topic.content = content
    topic.save(update_fields=["title", "content"])
    return topic


def _part(site: Site, spec: PartSpec) -> CoursePart:
    part = CoursePart._base_manager.filter(site=site, slug=spec.slug).first()
    if part is None:
        return cast(
            CoursePart, CoursePartFactory(site=site, slug=spec.slug, title=spec.title)
        )
    part.title = spec.title
    part.save(update_fields=["title"])
    return part


def _place(
    site: Site,
    collection: Course | CoursePart,
    child: Topic | CoursePart,
    order: int,
    due_date: date | None,
    due_time: time | None,
) -> ContentCollectionItem:
    """One placement of child in collection, carrying the given content deadline."""
    item = ContentCollectionItem._base_manager.filter(
        site=site,
        collection_type=DjangoContentType.objects.get_for_model(collection),
        collection_id=collection.pk,
        child_type=DjangoContentType.objects.get_for_model(child),
        child_id=child.pk,
    ).first()
    if item is None:
        item = cast(
            ContentCollectionItem,
            ContentCollectionItemFactory(
                site=site, collection_object=collection, child_object=child
            ),
        )
    item.order = order
    item.due_date = due_date
    item.due_time = due_time
    item.due_days_after_registration = None
    item.no_due_date = False
    item.save()
    return item


def _due(today: date, spec: TopicSpec) -> tuple[date | None, time | None]:
    if spec.due_in_days is None:
        return None, None
    return today + timedelta(days=spec.due_in_days), spec.due_time


def _build_course(
    site: Site, spec: CourseSpec, today: date
) -> tuple[Course, list[tuple[TopicSpec, ContentCollectionItem, Topic]]]:
    course = _course(site, spec)
    placed: list[tuple[TopicSpec, ContentCollectionItem, Topic]] = []
    for order, entry in enumerate(spec.items):
        if isinstance(entry, PartSpec):
            part = _part(site, entry)
            _place(site, course, part, order, None, None)
            for child_order, child in enumerate(entry.children):
                topic = _topic(site, child)
                item = _place(site, part, topic, child_order, *_due(today, child))
                placed.append((child, item, topic))
        else:
            topic = _topic(site, entry)
            item = _place(site, course, topic, order, *_due(today, entry))
            placed.append((entry, item, topic))
    return course, placed


def _record(site: Site, learner: Learner, course: Course) -> CourseProgress:
    registration = LearnerCourseRegistration._base_manager.filter(
        learner=learner, course=course
    ).first()
    if registration is None:
        registration = cast(
            LearnerCourseRegistration,
            LearnerCourseRegistrationFactory(
                site=site, learner=learner, course=course, is_active=True
            ),
        )
    elif not registration.is_active:
        registration.is_active = True
        registration.save()
    record = CourseProgress._base_manager.filter(
        learner=learner, course=course, learner_registration=registration
    ).first()
    if record is None:
        record = cast(
            CourseProgress,
            CourseProgressFactory(
                site=site,
                learner=learner,
                course=course,
                learner_registration=registration,
            ),
        )
    return record


def _apply_progress(
    site: Site,
    record: CourseProgress,
    placed: list[tuple[TopicSpec, ContentCollectionItem, Topic]],
) -> None:
    now = timezone.now()
    for spec, item, topic in placed:
        if spec.progress == UNTOUCHED:
            continue
        progress, _ = TopicProgress._base_manager.get_or_create(
            course_progress=record,
            collection_item=item,
            defaults={"site": site, "topic": topic},
        )
        progress.complete_time = now if spec.progress == COMPLETE else None
        # save() fires the signal that recalculates the record's percentage.
        progress.save()


def _partner_organisation(site: Site, name: str | None) -> Organisation:
    organisations = Organisation._base_manager.filter(site=site, is_default=False)
    organisation = (
        organisations.filter(name=name).first()
        if name
        else organisations.order_by("name").first()
    )
    if organisation is None:
        raise click.ClickException(
            f"No non-default organisation{f' named {name!r}' if name else ''} on "
            f"site '{site.name}'. Run: uv run python manage.py create_demo_data --yes"
        )
    return organisation


def _report(
    site: Site,
    course: Course,
    record: CourseProgress,
    placed: list[tuple[TopicSpec, ContentCollectionItem, Topic]],
) -> None:
    record.refresh_from_db()
    viewable_ids = [item.pk for item in course.viewable_collection_items()]
    click.secho(
        f"\n{course.title}  slug={course.slug}  organisation="
        f"{record.learner.organisation.name}  progress={record.progress_percentage}%",
        fg="green",
        bold=True,
    )
    for spec, item, _ in placed:
        index = viewable_ids.index(item.pk) + 1
        url = reverse(
            "learner_interface:view_course_item",
            kwargs={"course_slug": course.slug, "index": index},
        )
        due = f"{item.due_date} {item.due_time or ''}".strip() if item.due_date else "-"
        click.echo(f"  {index}. {spec.title!r}  due={due}  -> {spec.expected}  {url}")


@click.command()
@click.argument("site_name", default="DemoDev")
@click.option(
    "--learner-email",
    default="demodev@email.com",
    help="Existing user registered on the three courses.",
)
@click.option(
    "--organisation",
    "organisation_name",
    default=None,
    help="Non-default organisation for the partner course (default: first by name).",
)
def command(site_name: str, learner_email: str, organisation_name: str | None) -> None:
    """Build the deadline outline and dashboard scenario for one learner."""
    site = _get_site(site_name)
    user = User._base_manager.filter(email=learner_email).first()
    if user is None:
        raise click.ClickException(f"User '{learner_email}' not found.")
    zone = _ensure_time_zone(site)
    today = timezone.now().astimezone(zone).date()
    click.echo(f"Site zone {zone}; today is {today}.")

    default_learner = cast(
        Learner,
        LearnerFactory(
            user=user, organisation=get_default_organisation(site), site=site
        ),
    )
    partner_learner = cast(
        Learner,
        LearnerFactory(
            user=user,
            organisation=_partner_organisation(site, organisation_name),
            site=site,
        ),
    )

    for spec in (OUTLINE_COURSE, UPCOMING_COURSE, PARTNER_COURSE):
        course, placed = _build_course(site, spec, today)
        if spec is OUTLINE_COURSE:
            config = CourseDeadlineConfig._base_manager.filter(course=course).first()
            if config is None:
                config = cast(
                    CourseDeadlineConfig,
                    CourseDeadlineConfigFactory(site=site, course=course),
                )
            config.mark_overdue = DeadlineSwitch.ON
            config.close_items = DeadlineSwitch.ON
            config.grace_window = GRACE_WINDOW
            config.save()
        learner = default_learner if spec.in_default_organisation else partner_learner
        record = _record(site, learner, course)
        _apply_progress(site, record, placed)
        _report(site, Course._base_manager.get(pk=course.pk), record, placed)

    click.secho(
        f"\nLogin: {learner_email} at http://{site.domain}/ ; dashboard /",
        fg="yellow",
    )
