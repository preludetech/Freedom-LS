"""Seed a second site with its own ``start-here`` category and one course.

The dashboard's category sections are site-aware, but with all the demo content
sitting on a single site that is unobservable: "the other tenant's rows are
hidden" looks exactly like "there are no other rows". This command gives an
otherwise-empty site a category whose *slug* collides with DemoDev's
``start-here`` while its uuid does not, plus one published, freely accessible
course filed under it.

    CourseCategory  slug=start-here, show_on_dashboard=True, fresh uuid
    Course          "<Site> Only Course", published, access_type=free
                      dashboard_category -> that category
                      categories m2m     -> that category
    Topic           one lesson, placed in the course by a ContentCollectionItem

That is deliberately all of it. No learners, no registrations, no progress: the
isolation check is made anonymously against the target site's dashboard, and
the mirror-image check is that the *other* site's dashboard is unchanged.

Nothing outside the target site is read for writing, and the command refuses to
touch a category that the content loader owns (one with a ``file_path``), so
pointing it at a content-bearing site such as DemoDev fails loudly instead of
rewriting the declared row.

Re-running is a no-op: every row is looked up on ``(site, slug)`` -- the
per-site unique constraints -- and created only when missing, so the category's
uuid is stable across runs.
"""

from datetime import timedelta
from typing import cast

import djclick as click

from django.contrib.sites.models import Site
from django.utils.text import slugify

from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseCategoryFactory,
    CourseFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import (
    ContentCollectionItem,
    Course,
    CourseCategory,
    CourseVisibility,
    DifficultyLevel,
    Topic,
)

CATEGORY_SLUG = "start-here"
CATEGORY_TITLE = "Start here"
CATEGORY_DESCRIPTION = "New to the platform? Begin with these."


def _course_title(site: Site) -> str:
    """The course's title, e.g. ``Bloom Only Course``.

    Named after the site so a card that leaks into another tenant's dashboard
    announces where it came from without anyone having to check a pk.
    """
    return f"{site.name} Only Course"


def _get_site(site_name: str) -> Site:
    try:
        return Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        available = list(Site.objects.values_list("name", flat=True))
        raise click.ClickException(
            f"Site '{site_name}' not found. Available: {available}"
        ) from e


def _build_category(site: Site) -> tuple[CourseCategory, bool]:
    """The site's own ``start-here`` category. Returns ``(category, created)``.

    ``_base_manager``, not ``objects``: ``SiteAwareManager`` narrows to the
    thread-local request's site, and a management command has no request, so
    the default manager would answer for every site at once.

    A row carrying a ``file_path`` was written by the content loader from a
    declaration in a content repo. This fixture does not own such a row and
    will not edit one -- the uuid is pinned in the repo's yaml, and quietly
    changing anything about it here would be a change to declared content.
    """
    existing: CourseCategory | None = CourseCategory._base_manager.filter(
        site=site, slug=CATEGORY_SLUG
    ).first()
    if existing is not None:
        if existing.file_path:
            raise click.ClickException(
                f"Site '{site.name}' already has a '{CATEGORY_SLUG}' category "
                f"declared in content ({existing.file_path}, uuid={existing.pk}). "
                "This fixture only seeds sites with no content repo of their "
                "own -- pick an empty site."
            )
        return existing, False

    return cast(
        CourseCategory,
        CourseCategoryFactory(
            site=site,
            slug=CATEGORY_SLUG,
            title=CATEGORY_TITLE,
            description=CATEGORY_DESCRIPTION,
            order=0,
            show_on_dashboard=True,
        ),
    ), True


def _build_course(site: Site, category: CourseCategory) -> tuple[Course, bool]:
    """The site's single published, free course, filed under ``category``.

    Both category links are set: ``dashboard_category`` is what actually places
    the card in a section, and the ``categories`` m2m is set alongside it so the
    row matches what the content loader would have written.
    """
    title = _course_title(site)
    slug = slugify(title)
    existing: Course | None = Course._base_manager.filter(site=site, slug=slug).first()
    created = existing is None
    if existing is None:
        course = cast(
            Course,
            CourseFactory(
                site=site,
                title=title,
                slug=slug,
                description=(
                    f"The only course on the {site.name} site. It must never "
                    "appear on any other site's dashboard or catalogue."
                ),
                content=(
                    f"# {title}\n\nThis course exists only on the {site.name} "
                    "site, to prove that courses and categories do not leak "
                    "across tenants."
                ),
                access_config={"access_type": "free"},
                visibility=CourseVisibility.PUBLISHED,
                difficulty=DifficultyLevel.BEGINNER,
                estimated_duration=timedelta(minutes=10),
                learning_outcomes=[
                    f"Confirm this card is visible on {site.name} and nowhere else"
                ],
                dashboard_category=category,
            ),
        )
    else:
        course = existing
        course.dashboard_category = category
        course.visibility = CourseVisibility.PUBLISHED
        course.access_config = {"access_type": "free"}
        course.save(update_fields=["dashboard_category", "visibility", "access_config"])
    course.categories.set([category])
    return course, created


def _build_topic(site: Site, course: Course) -> tuple[Topic, bool]:
    """The course's single lesson, so it is not an empty outline."""
    title = f"{_course_title(site)} - Lesson 1"
    slug = slugify(title)
    existing: Topic | None = Topic._base_manager.filter(site=site, slug=slug).first()
    if existing is not None:
        return existing, False

    return cast(
        Topic,
        TopicFactory(
            site=site,
            title=title,
            slug=slug,
            content=(
                f"# {title}\n\nThe only lesson in {_course_title(site)}. "
                "Seeing it means you are on the right site."
            ),
        ),
    ), True


def _build_placement(
    site: Site, course: Course, topic: Topic
) -> tuple[ContentCollectionItem, bool]:
    """Place ``topic`` inside ``course`` as a viewable item."""
    existing: ContentCollectionItem | None = ContentCollectionItem._base_manager.filter(
        site=site, collection_id=course.pk, child_id=topic.pk
    ).first()
    if existing is not None:
        return existing, False

    return cast(
        ContentCollectionItem,
        ContentCollectionItemFactory(
            site=site, collection_object=course, child_object=topic, order=0
        ),
    ), True


def _report_slug_across_sites() -> None:
    """Every site holding the colliding slug, so the uuids can be compared."""
    click.secho(f"\n'{CATEGORY_SLUG}' categories, all sites:", fg="cyan", bold=True)
    for category in (
        CourseCategory._base_manager.filter(slug=CATEGORY_SLUG)
        .select_related("site")
        .order_by("site__name")
    ):
        click.secho(
            f"  {category.site.name:<10} ({category.site.domain:<14}) "
            f"uuid={category.pk} show_on_dashboard={category.show_on_dashboard} "
            f"courses={category.dashboard_courses.count()}",
            fg="cyan",
        )


@click.command()
@click.argument("site_name", default="Bloom")
def command(site_name: str) -> None:
    """Seed a colliding category slug plus one course on a second site.

    SITE_NAME is the site to create the data on (default: Bloom).
    """
    site = _get_site(site_name)

    category, category_created = _build_category(site)
    course, course_created = _build_course(site, category)
    topic, topic_created = _build_topic(site, course)
    placement, placement_created = _build_placement(site, course, topic)

    click.secho("\n--- Created / found ---", fg="cyan", bold=True)
    for label, obj, was_created in (
        ("CourseCategory", category, category_created),
        ("Course", course, course_created),
        ("Topic", topic, topic_created),
        ("ContentCollectionItem", placement, placement_created),
    ):
        click.secho(
            f"  {'NEW ' if was_created else 'kept'} {label:<22} "
            f"pk={obj.pk}  site={obj.site_id} ({obj.site.name})  {obj}",
            fg="green" if was_created else "yellow",
        )

    # Re-query: viewable_items() memoises, so the instance the placement was
    # hung off would still report an empty outline.
    fresh = Course._base_manager.get(pk=course.pk)
    click.secho(
        f"\n  {fresh.slug}: visibility={fresh.visibility} "
        f"access={fresh.access_config} "
        f"dashboard_category={fresh.dashboard_category.slug if fresh.dashboard_category else None} "
        f"categories={[c.slug for c in fresh.categories.all()]} "
        f"items={len(fresh.viewable_items())}",
        fg="green",
    )

    off_site = [
        f"{obj.__class__.__name__}(pk={obj.pk}, site={obj.site_id})"
        for obj in (category, course, topic, placement)
        if obj.site_id != site.id
    ]
    if off_site:
        raise click.ClickException(f"Rows landed on the wrong site: {off_site}")

    _report_slug_across_sites()

    click.secho(
        f"\nVerified: every row above carries site_id={site.id} ({site.name}).\n"
        f"Browse anonymously at http://{site.domain}/",
        fg="green",
        bold=True,
    )
