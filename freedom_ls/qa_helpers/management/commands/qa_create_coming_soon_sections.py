"""Seed the coming-soon dashboard-section fixtures (Seeds MIX, UNCAT, HIDDEN, ONLY).

Idempotently creates, on a single site (default: DemoDev), the four course
shapes the "Coming soon" dashboard QA needs. Everything is keyed on
``(slug, site)``, so a re-run updates rather than duplicates.

MIX
    ``CourseCategory`` "QA Soon Mix" (``qa-soon-mix``, shown, order 50) holding
    four courses: ``Mix Alpha`` / ``Mix Charlie`` / ``Mix Delta`` published and
    ``Mix Bravo`` coming soon. A coming-soon course whose dashboard category is
    shown renders in *both* that category's section and the Coming soon
    roll-up, so this category is the mixed-section case (and, at four courses,
    it also pages at ``SECTION_PAGE_SIZE`` = 3).

UNCAT
    ``Soon Uncategorised`` -- coming soon with no ``dashboard_category`` and no
    ``categories`` rows, so the Coming soon roll-up is its only home
    (``_discovery_pools`` keeps it out of ``rest`` entirely).

HIDDEN
    ``Soon Hidden`` -- coming soon in the existing ``reference-demo`` category,
    whose ``show_on_dashboard`` is False. Same story as UNCAT: it cannot reach
    the catch-all either, because ``rest`` only ever holds a coming-soon course
    with a *shown* category.

ONLY
    ``CourseCategory`` "QA Soon Only" (``qa-soon-only``, shown, order 0) with
    exactly one course, ``Soon Only One``, coming soon. A category section whose
    entire content is coming soon.

Every course is free, published-or-coming-soon (never hidden) and owns one
viewable Topic, so its card renders a "Free" access badge and its detail page
resolves.

No learner is registered on any of these courses and no ``RecommendedCourse``
points at one: both would pull the course out of the discovery sections, which
is the whole point of the seed. Each run re-checks and removes any such row that
has appeared since (a tester enrolling from the browser), reporting what it
removed.

The course shape follows ``qa_create_dashboard_paging_fixtures``, whose
``_ensure_topic`` / ``_get_site`` / ``_link_child`` helpers are reused here so
the cards render like the other seeded courses.
"""

from dataclasses import dataclass
from datetime import timedelta
from typing import cast

import djclick as click

from django.contrib.sites.models import Site

from freedom_ls.content_engine.factories import CourseCategoryFactory, CourseFactory
from freedom_ls.content_engine.models import (
    Course,
    CourseCategory,
    CourseVisibility,
    DifficultyLevel,
)
from freedom_ls.course_recommendations.models import RecommendedCourse
from freedom_ls.learner_management.models import (
    CohortCourseRegistration,
    LearnerCourseRegistration,
)
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.qa_helpers.management.commands.qa_create_dashboard_paging_fixtures import (
    _ensure_topic,
    _get_site,
    _link_child,
)

#: The category the HIDDEN seed borrows: it ships with the demo content and its
#: show_on_dashboard is False, which is the property the seed depends on.
HIDDEN_CATEGORY_SLUG = "reference-demo"

MIX_CATEGORY_SLUG = "qa-soon-mix"
ONLY_CATEGORY_SLUG = "qa-soon-only"


@dataclass(frozen=True)
class CategorySpec:
    """A ``CourseCategory`` this command owns outright."""

    slug: str
    title: str
    order: int
    show_on_dashboard: bool


@dataclass(frozen=True)
class CourseSpec:
    """One seeded course and where it should sit on the dashboard."""

    slug: str
    title: str
    visibility: str
    #: Slug of the dashboard category, or None for a deliberately
    #: uncategorised course (which also gets an empty ``categories`` m2m).
    category_slug: str | None
    note: str


MIX_CATEGORY = CategorySpec(
    slug=MIX_CATEGORY_SLUG, title="QA Soon Mix", order=50, show_on_dashboard=True
)
ONLY_CATEGORY = CategorySpec(
    slug=ONLY_CATEGORY_SLUG, title="QA Soon Only", order=0, show_on_dashboard=True
)
OWNED_CATEGORIES = [MIX_CATEGORY, ONLY_CATEGORY]

COURSE_SPECS = [
    CourseSpec(
        slug="qa-mix-alpha",
        title="Mix Alpha",
        visibility=CourseVisibility.PUBLISHED,
        category_slug=MIX_CATEGORY_SLUG,
        note="published sibling in the mixed category",
    ),
    CourseSpec(
        slug="qa-mix-bravo",
        title="Mix Bravo",
        visibility=CourseVisibility.COMING_SOON,
        category_slug=MIX_CATEGORY_SLUG,
        note="the coming-soon one in the mixed category",
    ),
    CourseSpec(
        slug="qa-mix-charlie",
        title="Mix Charlie",
        visibility=CourseVisibility.PUBLISHED,
        category_slug=MIX_CATEGORY_SLUG,
        note="published sibling in the mixed category",
    ),
    CourseSpec(
        slug="qa-mix-delta",
        title="Mix Delta",
        visibility=CourseVisibility.PUBLISHED,
        category_slug=MIX_CATEGORY_SLUG,
        note="published sibling in the mixed category",
    ),
    CourseSpec(
        slug="qa-soon-uncategorised",
        title="Soon Uncategorised",
        visibility=CourseVisibility.COMING_SOON,
        category_slug=None,
        note="coming soon with no category at all",
    ),
    CourseSpec(
        slug="qa-soon-hidden",
        title="Soon Hidden",
        visibility=CourseVisibility.COMING_SOON,
        category_slug=HIDDEN_CATEGORY_SLUG,
        note="coming soon in a category whose section is hidden",
    ),
    CourseSpec(
        slug="qa-soon-only-one",
        title="Soon Only One",
        visibility=CourseVisibility.COMING_SOON,
        category_slug=ONLY_CATEGORY_SLUG,
        note="the only course in an all-coming-soon category",
    ),
]


def _ensure_category(site: Site, spec: CategorySpec) -> CourseCategory:
    """Get or create the category keyed on (slug, site), resetting its fields.

    A re-run resets ``order`` / ``show_on_dashboard`` / ``title``: the whole
    point of the ONLY seed is where its section lands in the category order, so
    a value edited between runs has to be put back rather than left alone.
    """
    fields = {
        "title": spec.title,
        "order": spec.order,
        "show_on_dashboard": spec.show_on_dashboard,
    }
    category: CourseCategory | None = CourseCategory.objects.filter(
        slug=spec.slug, site=site
    ).first()
    if category is None:
        return cast(
            CourseCategory,
            CourseCategoryFactory(slug=spec.slug, site=site, **fields),
        )
    changed = {
        name: (getattr(category, name), value)
        for name, value in fields.items()
        if getattr(category, name) != value
    }
    if changed:
        for name, value in fields.items():
            setattr(category, name, value)
        category.save(update_fields=list(fields.keys()))
        for name, (was, now) in changed.items():
            click.secho(
                f"    reset {spec.slug}.{name}: {was!r} -> {now!r}", fg="yellow"
            )
    return category


def _get_existing_category(site: Site, slug: str) -> CourseCategory:
    """A category this command does not own, e.g. the demo ``reference-demo``."""
    try:
        found: CourseCategory = CourseCategory.objects.get(slug=slug, site=site)
        return found
    except CourseCategory.DoesNotExist as e:
        available = list(
            CourseCategory.objects.filter(site=site).values_list("slug", flat=True)
        )
        raise click.ClickException(
            f"CourseCategory '{slug}' not found on site '{site.name}'. "
            f"Available: {available}. Load the demo content first "
            f"(manage.py content_save ./demo_content {site.name})."
        ) from e


def _ensure_course(
    site: Site, spec: CourseSpec, category: CourseCategory | None
) -> Course:
    """One free, single-topic course in the state ``spec`` describes."""
    fields = {
        "title": spec.title,
        "description": (
            f"QA fixture: {spec.note}. Seeded for the dashboard "
            "coming-soon section pass."
        ),
        "content": (
            f"# {spec.title}\n\nA short QA course used to exercise the "
            "dashboard's coming-soon and category sections."
        ),
        "access_config": {"access_type": "free"},
        "visibility": spec.visibility,
        "difficulty": DifficultyLevel.BEGINNER,
        "estimated_duration": timedelta(minutes=15),
        "learning_outcomes": [f"Recognise the {spec.title} card on the dashboard"],
        "dashboard_category": category,
    }
    course: Course | None = Course.objects.filter(slug=spec.slug, site=site).first()
    if course is None:
        course = cast(Course, CourseFactory(slug=spec.slug, site=site, **fields))
    else:
        for name, value in fields.items():
            setattr(course, name, value)
        course.save(update_fields=list(fields.keys()))
    # The m2m follows the FK, except for the uncategorised seed, whose brief is
    # "no categories rows at all".
    course.categories.set([] if category is None else [category])

    topic = _ensure_topic(
        site,
        title=f"{spec.title} - Lesson 1",
        content=(
            f"# {spec.title}: Lesson 1\n\nThis is the only lesson in "
            f"{spec.title}. Marking it complete finishes the course."
        ),
    )
    _link_child(site, course=course, child=topic)
    # Re-query: viewable_items() memoises, so a course fetched before the link
    # would keep reporting an empty outline.
    return cast(Course, Course.objects.get(pk=course.pk))


def _strip_discovery_blockers(course: Course) -> list[str]:
    """Remove every row that would take ``course`` out of a discovery section.

    Registered and recommended courses are excluded from the discovery pool, so
    a registration a tester created by enrolling from the browser would silently
    empty the section on the next run. ``CourseProgress`` PROTECTs the
    registration, so it goes first.
    """
    removed: list[str] = []

    recommendations = RecommendedCourse.objects.filter(course=course)
    if recommendations.exists():
        emails = sorted(
            recommendations.select_related("user").values_list("user__email", flat=True)
        )
        counts = recommendations.delete()
        removed.append(f"RecommendedCourse for {emails}: {counts}")

    for registration in LearnerCourseRegistration.objects.filter(
        course=course
    ).select_related("learner__user"):
        email = registration.learner.user.email
        record_counts = CourseProgress.objects.filter(
            learner_registration=registration
        ).delete()
        registration_counts = registration.delete()
        removed.append(
            f"LearnerCourseRegistration {registration.pk} ({email}): "
            f"progress {record_counts}, registration {registration_counts}"
        )

    cohort_registrations = CohortCourseRegistration.objects.filter(course=course)
    if cohort_registrations.exists():
        names = sorted(
            cohort_registrations.select_related("cohort").values_list(
                "cohort__name", flat=True
            )
        )
        counts = cohort_registrations.delete()
        removed.append(f"CohortCourseRegistration for cohorts {names}: {counts}")

    return removed


def _describe(course: Course) -> str:
    return (
        f"{course.title} ({course.slug}) pk={course.pk} "
        f"visibility={course.visibility} access={course.access_config} "
        f"dashboard_category="
        f"{course.dashboard_category.slug if course.dashboard_category else None} "
        f"categories={[c.slug for c in course.categories.all()]} "
        f"viewable_items={len(course.viewable_items())} "
        f"registrations={LearnerCourseRegistration.objects.filter(course=course).count()} "
        f"recommendations={RecommendedCourse.objects.filter(course=course).count()}"
    )


@click.command()
@click.argument("site_name", default="DemoDev")
def command(site_name: str) -> None:
    """Seed the coming-soon dashboard-section fixtures (MIX, UNCAT, HIDDEN, ONLY).

    SITE_NAME is the site to create data on (default: DemoDev).
    """
    site = _get_site(site_name)
    click.secho(f"Site: {site.name} ({site.domain}) pk={site.pk}", fg="cyan", bold=True)

    click.secho("\n--- Categories ---", fg="cyan", bold=True)
    categories: dict[str, CourseCategory] = {}
    for category_spec in OWNED_CATEGORIES:
        category = _ensure_category(site, category_spec)
        categories[category_spec.slug] = category
        click.secho(
            f"  {category.title} ({category.slug}) pk={category.pk} "
            f"order={category.order} show_on_dashboard={category.show_on_dashboard}",
            fg="green",
        )
    hidden_category = _get_existing_category(site, HIDDEN_CATEGORY_SLUG)
    categories[HIDDEN_CATEGORY_SLUG] = hidden_category
    click.secho(
        f"  (existing) {hidden_category.title} ({hidden_category.slug}) "
        f"pk={hidden_category.pk} order={hidden_category.order} "
        f"show_on_dashboard={hidden_category.show_on_dashboard}",
        fg="cyan",
    )

    click.secho("\n--- Courses ---", fg="cyan", bold=True)
    for course_spec in COURSE_SPECS:
        course_category: CourseCategory | None = (
            None
            if course_spec.category_slug is None
            else categories[course_spec.category_slug]
        )
        course = _ensure_course(site, course_spec, course_category)
        for description in _strip_discovery_blockers(course):
            click.secho(f"  removed: {description}", fg="yellow")
        click.secho(f"  {_describe(course)}", fg="green")

    click.secho("\n--- Category sections, in dashboard order ---", fg="cyan", bold=True)
    for category in CourseCategory.objects.filter(site=site, show_on_dashboard=True):
        slugs = list(
            Course.objects.filter(site=site, dashboard_category=category)
            .order_by("slug")
            .values_list("slug", flat=True)
        )
        click.secho(f"  order={category.order} {category.slug}: {slugs}", fg="cyan")
