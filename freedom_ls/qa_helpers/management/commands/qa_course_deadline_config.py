"""Add (or update) or delete the ``CourseDeadlineConfig`` on one course.

``--action add`` writes the row with ``--mark-overdue`` (default ``off``) and leaves
every other switch at ``inherit`` unless given. ``--action delete`` prints the row, then
deletes it and prints the counts. Both print the resulting state.

Usage:
    uv run python manage.py qa_course_deadline_config \\
        --course-slug functionality-demo-course-parts --action add
    uv run python manage.py qa_course_deadline_config \\
        --course-slug functionality-demo-course-parts --action delete
"""

from typing import cast

import djclick as click

from django.contrib.sites.models import Site

from freedom_ls.content_engine.models import Course
from freedom_ls.deadlines.factories import CourseDeadlineConfigFactory
from freedom_ls.deadlines.models import CourseDeadlineConfig, DeadlineSwitch

SWITCH = click.Choice(DeadlineSwitch.values)


def _get_site(site_name: str) -> Site:
    try:
        return Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        available = list(Site.objects.values_list("name", flat=True))
        raise click.ClickException(
            f"Site '{site_name}' not found. Available: {available}"
        ) from e


def _describe(config: CourseDeadlineConfig) -> str:
    return (
        f"{config.pk} [{config.site.name}] {config}: mark_overdue={config.mark_overdue} "
        f"close_items={config.close_items} end_course_access={config.end_course_access} "
        f"grace_window={config.grace_window} after_access_ended={config.after_access_ended}"
    )


@click.command()
@click.option("--course-slug", required=True, help="Course slug.")
@click.option("--action", type=click.Choice(["add", "delete"]), required=True)
@click.option("--mark-overdue", type=SWITCH, default=DeadlineSwitch.OFF.value)
@click.option("--close-items", type=SWITCH, default=DeadlineSwitch.INHERIT.value)
@click.option("--end-course-access", type=SWITCH, default=DeadlineSwitch.INHERIT.value)
@click.option("--site-name", default="DemoDev", help="Site the course lives on.")
def command(
    course_slug: str,
    action: str,
    mark_overdue: str,
    close_items: str,
    end_course_access: str,
    site_name: str,
) -> None:
    """Add or delete COURSE_SLUG's CourseDeadlineConfig."""
    site = _get_site(site_name)
    course = Course._base_manager.filter(site=site, slug=course_slug).first()
    if course is None:
        raise click.ClickException(f"Course '{course_slug}' not on '{site_name}'.")
    existing = CourseDeadlineConfig._base_manager.filter(course=course).select_related(
        "site"
    )

    if action == "delete":
        for config in existing:
            click.echo(f"Removing {_describe(config)}")
        click.echo(f"Removed: {existing.delete()}")
        click.echo(f"Remaining for {course_slug}: {existing.count()}")
        return

    config = existing.first() or cast(
        CourseDeadlineConfig, CourseDeadlineConfigFactory(site=site, course=course)
    )
    config.mark_overdue = mark_overdue
    config.close_items = close_items
    config.end_course_access = end_course_access
    config.full_clean()
    config.save()
    click.secho(f"Saved {_describe(config)}", fg="green")
