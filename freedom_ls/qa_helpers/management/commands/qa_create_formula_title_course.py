"""Seed a published, free course whose title is a spreadsheet formula.

For CSV-injection checks on any export that writes a course title: the title
starts with ``=`` so an unescaped export cell would be evaluated by a
spreadsheet. The course mirrors the demo course "Functionality Demo - show end
with Topic": published, ``access_type`` free, audience organisation_learners
with no organisation links (so open to every signed-in learner), no
application form, no price. It holds one Topic so the player opens.

Idempotent, keyed on (slug, site): re-running refreshes the course and topic
fields in place and never duplicates the collection item. Touches nothing else.

Usage:
    uv run python manage.py qa_create_formula_title_course [--site-name DemoDev]
"""

from typing import cast

import djclick as click

from django.contrib.contenttypes.models import ContentType as DjangoContentType

from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import (
    ContentCollectionItem,
    Course,
    CourseVisibility,
    Topic,
)
from freedom_ls.qa_helpers.management.commands.qa_create_clean_applicant import (
    _get_site,
)

COURSE_TITLE = '=HYPERLINK("http://example.com","QA formula course")'
COURSE_SLUG = "qa-formula-course"
TOPIC_TITLE = "QA formula course topic"
TOPIC_SLUG = "qa-formula-course-topic"
TOPIC_CONTENT = (
    "# QA formula course\n\n"
    "The only item of a course whose title is a spreadsheet formula, for "
    "CSV-injection checks.\n"
)
COURSE_FIELDS: dict[str, object] = {
    "title": COURSE_TITLE,
    "description": "A course whose title starts with an equals sign.",
    "visibility": CourseVisibility.PUBLISHED,
    "access_config": {"access_type": "free"},
    "application_form": None,
}


@click.command()
@click.option("--site-name", default="DemoDev", help="Site name (default DemoDev).")
def command(site_name: str) -> None:
    """Create or refresh the formula-title course and its one topic."""
    site = _get_site(site_name)

    course = Course._base_manager.filter(site=site, slug=COURSE_SLUG).first()
    if course is None:
        course = cast(
            Course, CourseFactory(slug=COURSE_SLUG, site=site, **COURSE_FIELDS)
        )
        click.secho(f"  Created course pk={course.pk}", fg="green")
    else:
        Course._base_manager.filter(pk=course.pk).update(**COURSE_FIELDS)
        click.secho(f"  Refreshed course pk={course.pk}", fg="yellow")

    topic = Topic._base_manager.filter(site=site, slug=TOPIC_SLUG).first()
    if topic is None:
        topic = cast(
            Topic,
            TopicFactory(
                title=TOPIC_TITLE, slug=TOPIC_SLUG, content=TOPIC_CONTENT, site=site
            ),
        )
    else:
        Topic._base_manager.filter(pk=topic.pk).update(
            title=TOPIC_TITLE, content=TOPIC_CONTENT
        )

    if not ContentCollectionItem._base_manager.filter(
        collection_type=DjangoContentType.objects.get_for_model(Course),
        collection_id=course.pk,
        child_type=DjangoContentType.objects.get_for_model(Topic),
        child_id=topic.pk,
        site=site,
    ).exists():
        ContentCollectionItemFactory(
            collection_object=course, child_object=topic, order=0, site=site
        )

    fresh = Course._base_manager.get(pk=course.pk)
    stored_as_is = fresh.title == COURSE_TITLE
    click.secho("\n== Formula-title course ==", fg="cyan", bold=True)
    click.echo(f"  title      {fresh.title!r} (stored as-is: {stored_as_is})")
    click.echo(f"  slug       {fresh.slug}")
    click.echo(f"  visibility {fresh.visibility}  access {fresh.access_config}")
    click.echo(f"  items      {len(fresh.viewable_items())}")
    click.echo(f"  detail     /courses/{fresh.slug}/detail/")
    click.echo(f"  access     /courses/{fresh.slug}/access/")
    if not stored_as_is:
        raise click.ClickException("Title was not stored as-is.")
