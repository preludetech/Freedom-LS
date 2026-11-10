"""Finish the deadlines frontend QA seed: §0.3 steps 3 to 5 of the deadlines QA plan.

Run it after ``qa_create_deadlines_seed``, and again after every re-run of that command:
the seed deletes and rebuilds the fresh learner's registrations, which takes this
command's override and registration with them.

On the named site it:

* gives ``qa_deadline_fresh@email.com`` a fixed ``LearnerDeadlineOverride`` on the parts
  course's "What to Expect" placement, due today (site zone) at 23:59 (*the today item*);
* builds ``QA Long Deadline Titles`` (slug ``qa-long-deadline-titles``): a long-titled
  topic due 2020-01-01, then "Second topic" with no due date, belonging to
  ``QA Deadlines Org``, and registers the fresh learner on it individually through their
  ``QA Deadlines Org`` learner, so the dashboard card carries the organisation byline;
* deletes any ``SiteDeadlineConfig`` on the site, any ``OrganisationDeadlineConfig`` on
  ``QA Deadlines Org`` and any ``CourseDeadlineConfig`` on the parts, plain and long-title
  courses, printing each row before it goes.

Idempotent.

Usage:
    uv run python manage.py qa_create_deadlines_seed_extras [--site-name DemoDev]
"""

from datetime import date, time
from typing import cast

import djclick as click

from django.contrib.sites.models import Site
from django.db.models import QuerySet
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import Course
from freedom_ls.deadlines.models import (
    CourseDeadlineConfig,
    DeadlineKind,
    LearnerDeadlineOverride,
    OrganisationDeadlineConfig,
    SiteDeadlineConfig,
)
from freedom_ls.learner_management.models import Learner
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.organisations.models import Organisation
from freedom_ls.qa_helpers.management.commands.qa_create_deadline_outline_scenario import (
    CourseSpec,
    TopicSpec,
    _course,
    _place,
    _record,
    _topic,
)
from freedom_ls.qa_helpers.management.commands.qa_create_deadlines_seed import (
    FRESH_EMAIL,
    ORG_NAME,
    PARTS_SLUG,
    PLAIN_SLUG,
    _get_course,
    _get_site,
    _item_titled,
)
from freedom_ls.site_aware_models.time_zones import site_time_zone

TODAY_ITEM_TITLE = "What to Expect"
END_OF_DAY = time(23, 59)
LONG_SLUG = "qa-long-deadline-titles"
LONG_TOPIC_DUE = date(2020, 1, 1)
LONG_COURSE = CourseSpec(
    slug=LONG_SLUG,
    title="QA Long Deadline Titles",
    in_default_organisation=False,
    items=(
        TopicSpec(
            "qa-long-deadline-titles-long-topic",
            "A deliberately long topic title that cannot fit a phone outline row "
            "beside its date",
            None,
            None,
            "untouched",
            "MISSED, due 2020-01-01; the title truncates at 375px",
        ),
        TopicSpec(
            "qa-long-deadline-titles-second-topic",
            "Second topic",
            None,
            None,
            "untouched",
            "no deadline",
        ),
    ),
)


def _fresh_learner(site: Site) -> Learner:
    user = User._base_manager.filter(email=FRESH_EMAIL).first()
    organisation = Organisation._base_manager.filter(site=site, name=ORG_NAME).first()
    learner = (
        Learner._base_manager.filter(user=user, organisation=organisation).first()
        if user and organisation
        else None
    )
    if learner is None:
        raise click.ClickException(
            f"{FRESH_EMAIL} has no learner in '{ORG_NAME}'. Run: "
            f"uv run python manage.py qa_create_deadlines_seed --site-name {site.name}"
        )
    return learner


def _today_override(
    site: Site, learner: Learner, parts: Course
) -> LearnerDeadlineOverride:
    record = CourseProgress._base_manager.filter(
        learner=learner, course=parts, learner_registration__isnull=False
    ).first()
    if record is None:
        raise click.ClickException(
            f"{FRESH_EMAIL} has no parts-course record. Run qa_create_deadlines_seed."
        )
    today = timezone.now().astimezone(site_time_zone(site)).date()
    override, created = LearnerDeadlineOverride._base_manager.update_or_create(
        course_progress=record,
        collection_item=_item_titled(parts, TODAY_ITEM_TITLE),
        defaults={
            "site": site,
            "kind": DeadlineKind.FIXED,
            "due_date": today,
            "due_time": END_OF_DAY,
            "due_days_after_registration": None,
        },
    )
    override.full_clean()
    click.echo(
        f"{'Created' if created else 'Updated'} today override {override.pk}: "
        f"{TODAY_ITEM_TITLE!r} due {today} {END_OF_DAY} (record {record.pk})."
    )
    return override


def _long_course(site: Site, learner: Learner) -> Course:
    course = _course(site, LONG_COURSE)
    # The course detail page names Course.organisations; the dashboard card names the
    # record's learner organisation. Both are QA Deadlines Org.
    course.organisations.set([learner.organisation])
    for order, spec in enumerate(LONG_COURSE.items):
        topic_spec = cast(TopicSpec, spec)
        topic = _topic(site, topic_spec)
        due = LONG_TOPIC_DUE if order == 0 else None
        item = _place(site, course, topic, order, due, None)
        click.echo(
            f"Topic {topic.pk} {topic.title!r}; placement {item.pk} order {order} due {due}"
        )
    record = _record(site, learner, course)
    click.echo(
        f"Course {course.pk} {course.title!r}; registration "
        f"{record.learner_registration_id}; record {record.pk} "
        f"(learner {learner.pk} in {learner.organisation.name})"
    )
    return course


def _delete_rows(label: str, queryset: QuerySet) -> None:
    rows = list(queryset.select_related("site"))
    for row in rows:
        click.echo(f"Removing {label} {row.pk} [{row.site.name}] {row}")
    click.echo(f"{label} removed: {queryset.delete()}")


def _strip_layer_configs(site: Site, courses: list[Course]) -> None:
    _delete_rows(
        "SiteDeadlineConfig", SiteDeadlineConfig._base_manager.filter(site=site)
    )
    _delete_rows(
        "OrganisationDeadlineConfig",
        OrganisationDeadlineConfig._base_manager.filter(
            site=site, organisation__name=ORG_NAME
        ),
    )
    _delete_rows(
        "CourseDeadlineConfig",
        CourseDeadlineConfig._base_manager.filter(course__in=courses),
    )


@click.command()
@click.option("--site-name", default="DemoDev", help="Site the data belongs to.")
def command(site_name: str) -> None:
    """Add the today item, the long-title course and strip layer configs on SITE_NAME."""
    site = _get_site(site_name)
    parts = _get_course(site, PARTS_SLUG, site_name)
    plain = _get_course(site, PLAIN_SLUG, site_name)
    learner = _fresh_learner(site)

    _today_override(site, learner, parts)
    long_course = _long_course(site, learner)
    _strip_layer_configs(site, [parts, plain, long_course])

    for course in (parts, long_course):
        click.secho(f"\n{course.title} ({course.slug})", fg="green", bold=True)
        for index, item in enumerate(course.viewable_collection_items(), start=1):
            url = reverse(
                "learner_interface:view_course_item",
                kwargs={"course_slug": course.slug, "index": index},
            )
            click.echo(f"  {url}  {getattr(item.child, 'title', '')}")
