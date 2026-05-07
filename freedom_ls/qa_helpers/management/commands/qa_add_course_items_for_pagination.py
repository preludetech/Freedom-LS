"""Add extra Topic items to a Course so the educator course-progress column paginator paginates.

The educator interface course-progress panel paginates course items (topics + forms,
excluding CourseParts) at COLUMN_PAGE_SIZE per page. To exercise the column paginator
we need >COLUMN_PAGE_SIZE items. This command appends a CoursePart "QA Pagination Test
Section" containing N extra topics to the target course so the total flat item count
exceeds the threshold.

Idempotent: re-running will reuse the existing QA CoursePart and only add the topics
that are missing.
"""

import djclick as click

from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.db.models import Max

from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CoursePartFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import (
    ContentCollectionItem,
    Course,
    CoursePart,
    Topic,
)

QA_PART_SLUG = "qa-pagination-test-section"
QA_PART_TITLE = "QA Pagination Test Section"
QA_TOPIC_SLUG_PREFIX = "qa-pagination-topic"


def _count_flat_items(course: Course) -> int:
    """Count topics+forms (excluding CourseParts) reachable from the course."""
    return len(course.viewable_items())


@click.command()
@click.argument("site_name")
@click.option(
    "--course-slug",
    default="functionality-demo-course-parts",
    help="Slug of the course to extend (default: functionality-demo-course-parts)",
)
@click.option(
    "--target-item-count",
    default=18,
    type=int,
    help="Desired total number of flat course items (topics+forms). Default 18.",
)
def command(
    site_name: str,
    course_slug: str,
    target_item_count: int,
) -> None:
    """Pad a course with extra topics to exceed the column-pagination threshold.

    SITE_NAME is the name of the site to operate on (e.g. 'DemoDev').
    """
    try:
        site = Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        available = list(Site.objects.values_list("name", flat=True))
        raise click.ClickException(
            f"Site '{site_name}' not found. Available: {available}"
        ) from e

    try:
        course = Course.objects.get(slug=course_slug, site=site)
    except Course.DoesNotExist as e:
        available = list(
            Course.objects.filter(site=site).values_list("slug", flat=True)
        )
        raise click.ClickException(
            f"Course '{course_slug}' not found on site '{site_name}'. "
            f"Available: {available}"
        ) from e

    initial_count = _count_flat_items(course)
    click.secho(
        f"Course: {course.title} (current flat item count: {initial_count})",
        fg="cyan",
    )

    if initial_count >= target_item_count:
        click.secho(
            f"Course already has {initial_count} items (>= target "
            f"{target_item_count}). Nothing to do.",
            fg="yellow",
        )
        return

    # Get or create the QA CoursePart
    try:
        qa_part = CoursePart.objects.get(slug=QA_PART_SLUG, site=site)
        click.secho(f"Reusing existing CoursePart '{qa_part.title}'", fg="yellow")
    except CoursePart.DoesNotExist:
        qa_part = CoursePartFactory(title=QA_PART_TITLE, slug=QA_PART_SLUG, site=site)
        click.secho(f"Created CoursePart '{qa_part.title}'", fg="green")

    # Attach the QA CoursePart to the course as a top-level item if not present
    course_ctype = ContentType.objects.get_for_model(Course)
    coursepart_ctype = ContentType.objects.get_for_model(CoursePart)
    topic_ctype = ContentType.objects.get_for_model(Topic)

    qa_part_in_course = ContentCollectionItem.objects.filter(
        collection_type=course_ctype,
        collection_id=course.pk,
        child_type=coursepart_ctype,
        child_id=qa_part.pk,
        site=site,
    ).exists()

    if not qa_part_in_course:
        next_order = (
            ContentCollectionItem.objects.filter(
                collection_type=course_ctype, collection_id=course.pk, site=site
            ).aggregate(Max("order"))["order__max"]
            or 0
        ) + 1
        cci = ContentCollectionItemFactory(
            collection_object=course,
            child_object=qa_part,
            order=next_order,
            site=site,
        )
        click.secho(
            f"Attached '{qa_part.title}' to course at order={cci.order}",
            fg="green",
        )
    else:
        click.secho(f"'{qa_part.title}' already attached to course", fg="yellow")

    # Pad with topics until we hit target_item_count
    items_needed = target_item_count - initial_count
    click.secho(
        f"Need to add {items_needed} topic(s) to reach target {target_item_count}",
        fg="cyan",
    )

    # Determine starting topic index by inspecting existing QA topics in the part
    next_part_order = ContentCollectionItem.objects.filter(
        collection_type=coursepart_ctype, collection_id=qa_part.pk, site=site
    ).aggregate(Max("order"))["order__max"]
    next_part_order = 0 if next_part_order is None else next_part_order + 1

    added = 0
    idx = 1
    while added < items_needed:
        slug = f"{QA_TOPIC_SLUG_PREFIX}-{idx:02d}"
        try:
            topic = Topic.objects.get(slug=slug, site=site)
        except Topic.DoesNotExist:
            topic = TopicFactory(
                title=f"QA Pagination Topic {idx:02d}",
                slug=slug,
                site=site,
            )

        already_attached = ContentCollectionItem.objects.filter(
            collection_type=coursepart_ctype,
            collection_id=qa_part.pk,
            child_type=topic_ctype,
            child_id=topic.pk,
            site=site,
        ).exists()

        if not already_attached:
            ContentCollectionItemFactory(
                collection_object=qa_part,
                child_object=topic,
                order=next_part_order,
                site=site,
            )
            next_part_order += 1
            added += 1
            click.secho(f"  + Added topic '{topic.title}'", fg="green")
        idx += 1

        # Safety net to prevent runaway loops
        if idx > items_needed + 100:
            raise click.ClickException(
                "Could not reach target after many attempts; aborting."
            )

    final_count = _count_flat_items(course)
    click.secho("\n--- Summary ---", fg="cyan", bold=True)
    click.secho(f"Site:           {site.name}", fg="cyan")
    click.secho(f"Course:         {course.title} (pk={course.pk})", fg="cyan")
    click.secho(f"Item count:     {initial_count} -> {final_count}", fg="cyan")
    click.secho(f"Topics added:   {added}", fg="cyan")
