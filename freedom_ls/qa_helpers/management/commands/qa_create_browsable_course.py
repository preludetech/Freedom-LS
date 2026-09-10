"""Seed the minimum data needed to browse a course in the browser.

Built for a dev database whose Course table is EMPTY: it creates, on one site
(default DemoDev), a single published/free course that

  1. appears on the public course listing at ``/courses/``,
  2. holds one CoursePart containing three markdown Topics, so the course player
     and its TOC/navigation HTMX partials have real pages to render, and
  3. is registered to an existing user (default ``demodev@email.com``), via a
     Learner in the site's default Organisation plus a
     LearnerCourseRegistration, so the logged-in player works end to end.

Everything is built with the site-aware factories and an explicit ``site=``
override (the factories' thread-local site default is None outside a request).

Idempotent: re-running refreshes the course/part/topic fields in place, keyed on
(slug, site), and never duplicates the ContentCollectionItem rows or the
registration.
"""

from typing import cast

import djclick as click

from django.contrib.contenttypes.models import ContentType as DjangoContentType
from django.contrib.sites.models import Site
from django.urls import reverse

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
from freedom_ls.learner_management.factories import (
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import Learner, LearnerCourseRegistration
from freedom_ls.organisations.utils import get_default_organisation

COURSE_TITLE = "QA Browsable Course"
COURSE_SLUG = "qa-browsable-course"
COURSE_DESCRIPTION = (
    "A minimal end-to-end course for manual QA of the catalogue, the course "
    "detail page and the course player."
)
COURSE_CONTENT = (
    "## About this course\n\n"
    "This course exists purely so a human can *browse* one in the browser. It "
    "has a single part with three short topics.\n"
)

PART_TITLE = "Part 1: Getting Started"
PART_SLUG = "qa-browsable-part-1"

# (slug, title, markdown content) in player order.
TOPICS: list[tuple[str, str, str]] = [
    (
        "qa-browsable-welcome",
        "Welcome",
        "# Welcome\n\n"
        "This is the **first** topic of the QA browsable course.\n\n"
        "- It renders real markdown\n"
        "- It has a list, so the prose styles are visible\n"
        "- It is item 1 in the player\n\n"
        "> Use the Next button to move on.\n",
    ),
    (
        "qa-browsable-key-ideas",
        "Key Ideas",
        "# Key Ideas\n\n"
        "The second topic exists so the player's *Previous* and *Next* "
        "navigation both have somewhere to go.\n\n"
        "## A sub-heading\n\n"
        "Some inline `code`, a [link](https://example.com) and a second "
        "paragraph so the topic is not a single line.\n\n"
        "1. First\n2. Second\n3. Third\n",
    ),
    (
        "qa-browsable-wrap-up",
        "Wrap Up",
        "# Wrap Up\n\n"
        "The final topic. Completing it should take the course to 100% and "
        "surface the course-finish page.\n\n"
        "| Column | Value |\n| --- | --- |\n| Topics | 3 |\n| Parts | 1 |\n",
    ),
]


def _get_or_create_course(site: Site) -> Course:
    """Create (or refresh) the published, free QA course on ``site``."""
    course: Course | None = Course.objects.filter(slug=COURSE_SLUG, site=site).first()
    if course is None:
        return cast(
            Course,
            CourseFactory(
                title=COURSE_TITLE,
                slug=COURSE_SLUG,
                description=COURSE_DESCRIPTION,
                content=COURSE_CONTENT,
                visibility=CourseVisibility.PUBLISHED,
                access_config={"access_type": "free"},
                site=site,
            ),
        )
    course.title = COURSE_TITLE
    course.description = COURSE_DESCRIPTION
    course.content = COURSE_CONTENT
    course.visibility = CourseVisibility.PUBLISHED
    course.access_config = {"access_type": "free"}
    course.save(
        update_fields=[
            "title",
            "description",
            "content",
            "visibility",
            "access_config",
        ]
    )
    return course


def _get_or_create_part(site: Site) -> CoursePart:
    """Create (or refresh) the course's single CoursePart."""
    part: CoursePart | None = CoursePart.objects.filter(
        slug=PART_SLUG, site=site
    ).first()
    if part is None:
        return cast(
            CoursePart,
            CoursePartFactory(title=PART_TITLE, slug=PART_SLUG, site=site),
        )
    part.title = PART_TITLE
    part.save(update_fields=["title"])
    return part


def _get_or_create_topic(site: Site, *, slug: str, title: str, content: str) -> Topic:
    """Create (or refresh) one markdown Topic."""
    topic: Topic | None = Topic.objects.filter(slug=slug, site=site).first()
    if topic is None:
        return cast(
            Topic,
            TopicFactory(title=title, slug=slug, content=content, site=site),
        )
    topic.title = title
    topic.content = content
    topic.save(update_fields=["title", "content"])
    return topic


def _ensure_item(
    site: Site,
    *,
    collection: Course | CoursePart,
    child: CoursePart | Topic,
    order: int,
) -> None:
    """Ensure exactly one ContentCollectionItem places ``child`` in ``collection``."""
    existing = ContentCollectionItem.objects.filter(
        collection_type=DjangoContentType.objects.get_for_model(collection),
        collection_id=collection.pk,
        child_type=DjangoContentType.objects.get_for_model(child),
        child_id=child.pk,
        site=site,
    ).first()
    if existing is not None:
        if existing.order != order:
            existing.order = order
            existing.save(update_fields=["order"])
        return
    ContentCollectionItemFactory(
        collection_object=collection, child_object=child, order=order, site=site
    )


def _ensure_registration(site: Site, user: User, course: Course) -> Learner:
    """Ensure the user has a Learner in the site's default org and is registered."""
    learner = cast(
        Learner,
        LearnerFactory(
            user=user, organisation=get_default_organisation(site), site=site
        ),
    )
    if not LearnerCourseRegistration.objects.filter(
        learner=learner, course=course, site=site
    ).exists():
        LearnerCourseRegistrationFactory(
            learner=learner, course=course, site=site, is_active=True
        )
    return learner


@click.command()
@click.argument("site_name", default="DemoDev")
@click.option(
    "--learner-email",
    default="demodev@email.com",
    help="Existing user to register on the course.",
)
def command(site_name: str, learner_email: str) -> None:
    """Create one browsable published course (1 part, 3 topics) and register a user.

    SITE_NAME is the site to create data on (default: DemoDev).
    """
    try:
        site = Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        available = list(Site.objects.values_list("name", flat=True))
        raise click.ClickException(
            f"Site '{site_name}' not found. Available: {available}"
        ) from e

    user: User | None = User.objects.filter(email=learner_email, site=site).first()
    if user is None:
        raise click.ClickException(
            f"User '{learner_email}' not found on site '{site_name}'. "
            "This command registers an EXISTING user; create one first."
        )

    course = _get_or_create_course(site)
    part = _get_or_create_part(site)
    _ensure_item(site, collection=course, child=part, order=0)
    for order, (slug, title, content) in enumerate(TOPICS):
        topic = _get_or_create_topic(site, slug=slug, title=title, content=content)
        _ensure_item(site, collection=part, child=topic, order=order)

    learner = _ensure_registration(site, user, course)

    # Re-query: Course.children()/collection_items() are memoized per instance,
    # so the instance we just added items to would report a stale tree.
    fresh = Course.objects.get(pk=course.pk)
    viewables = fresh.viewable_items()

    click.secho("\n--- Browsable course QA data ---", fg="cyan", bold=True)
    click.secho(f"Site: {site.name} (pk={site.pk}, domain={site.domain})", fg="cyan")
    click.secho(
        f"Course: {fresh.title}  slug={fresh.slug}  visibility={fresh.visibility}  "
        f"access_config={fresh.access_config}",
        fg="green",
    )
    click.secho(f"CoursePart: {part.title} (slug={part.slug})", fg="green")
    click.secho(f"Viewable items: {len(viewables)}", fg="green")
    listing_url = reverse("learner_interface:courses")
    detail_url = reverse(
        "learner_interface:course_detail", kwargs={"course_slug": fresh.slug}
    )
    home_url = reverse(
        "learner_interface:course_home", kwargs={"course_slug": fresh.slug}
    )
    click.secho(f"Listing:      http://{site.domain}{listing_url}", fg="yellow")
    click.secho(f"Detail:       http://{site.domain}{detail_url}", fg="yellow")
    click.secho(f"Player (home):http://{site.domain}{home_url}", fg="yellow")
    for index, item in enumerate(viewables, start=1):
        item_url = reverse(
            "learner_interface:view_course_item",
            kwargs={"course_slug": fresh.slug, "index": index},
        )
        click.secho(
            f"  item {index}: {item.title}  ->  http://{site.domain}{item_url}",
            fg="yellow",
        )
    click.secho(
        f"Registered: {user.email} (user pk={user.pk}) via Learner pk={learner.pk} "
        f"in organisation '{learner.organisation.name}'",
        fg="green",
        bold=True,
    )
