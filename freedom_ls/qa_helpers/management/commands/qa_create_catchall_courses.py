"""Seed the two filler courses that make the dashboard's catch-all section page.

Idempotently creates, on a single site (default: DemoDev), two published, free
courses -- ``Catchall One`` and ``Catchall Two`` -- each with a single topic and
**no** ``dashboard_category`` and **no** ``categories`` m2m rows, so they fall
through every category section into the dashboard's catch-all "Available
courses" section.

With the demo courses that already land there (a course whose dashboard
category is hidden lands in the catch-all too) the section holds enough courses
to page at ``SECTION_PAGE_SIZE``, which is what makes it possible to check that
one section's pagination links preserve another section's page state.

No learner is registered on these courses and no ``RecommendedCourse`` points at
them: registered courses are excluded from the discovery sections, which would
undo the whole point of the seed.

The course shape follows ``qa_create_dashboard_paging_fixtures``, whose
``_ensure_topic`` / ``_link_child`` helpers are reused here so the cards render
like the other seeded courses.
"""

from datetime import timedelta
from typing import cast

import djclick as click

from django.contrib.sites.models import Site

from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import Course, CourseVisibility, DifficultyLevel
from freedom_ls.qa_helpers.management.commands.qa_create_dashboard_paging_fixtures import (
    _ensure_topic,
    _get_site,
    _link_child,
)

CATCHALL_WORDS = ["One", "Two"]
CATCHALL_SLUGS = [f"catchall-{word.lower()}" for word in CATCHALL_WORDS]


def _ensure_catchall_course(site: Site, word: str) -> Course:
    """One published, free, *uncategorised* ``Catchall <word>`` course."""
    title = f"Catchall {word}"
    slug = f"catchall-{word.lower()}"
    fields = {
        "title": title,
        "description": (
            f"Filler course {word}, seeded so the dashboard's catch-all "
            "'Available courses' section has enough courses to page."
        ),
        "content": (
            f"# {title}\n\nA short QA course used to exercise dashboard "
            "pagination. Open the lesson below to start it."
        ),
        "access_config": {"access_type": "free"},
        "visibility": CourseVisibility.PUBLISHED,
        "difficulty": DifficultyLevel.BEGINNER,
        "estimated_duration": timedelta(minutes=15),
        "learning_outcomes": [f"Recognise the {title} card on the dashboard"],
        # The point of the fixture: no dashboard category, so the course falls
        # through to the catch-all section.
        "dashboard_category": None,
    }
    course: Course | None = Course.objects.filter(slug=slug, site=site).first()
    if course is None:
        course = cast(Course, CourseFactory(slug=slug, site=site, **fields))
    else:
        for name, value in fields.items():
            setattr(course, name, value)
        course.save(update_fields=list(fields.keys()))
    # Also empty, so no category section can claim the course either.
    course.categories.set([])

    topic = _ensure_topic(
        site,
        title=f"{title} - Lesson 1",
        content=(
            f"# {title}: Lesson 1\n\nThis is the only lesson in {title}. "
            "Marking it complete finishes the course."
        ),
    )
    _link_child(site, course=course, child=topic)
    # Re-query: viewable_items() memoises, so a course fetched before the link
    # would keep reporting an empty outline.
    return cast(Course, Course.objects.get(pk=course.pk))


@click.command()
@click.argument("site_name", default="DemoDev")
def command(site_name: str) -> None:
    """Seed the uncategorised Catchall courses for the "Available courses" section.

    SITE_NAME is the site to create data on (default: DemoDev).
    """
    site = _get_site(site_name)
    click.secho(f"Site: {site.name} ({site.domain})", fg="cyan", bold=True)

    for word in CATCHALL_WORDS:
        course = _ensure_catchall_course(site, word)
        click.secho(
            f"  {course.title} ({course.slug}) visibility={course.visibility} "
            f"access={course.access_config} dashboard_category="
            f"{course.dashboard_category.slug if course.dashboard_category else None} "
            f"categories={[c.slug for c in course.categories.all()]} "
            f"items={len(course.viewable_items())}",
            fg="green",
        )

    click.secho("\nCourse slugs on this site:", fg="cyan", bold=True)
    for slug in (
        Course.objects.filter(site=site).order_by("slug").values_list("slug", flat=True)
    ):
        click.secho(f"  {slug}", fg="cyan")
