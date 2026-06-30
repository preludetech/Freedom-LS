"""Create QA data for the "Coming Soon & Hidden Courses" course-visibility feature.

Seeds (idempotently) on a single site (default: DemoDev) the full data shape a
manual browser QA pass needs for course visibility:

ACCOUNTS (both login-ready: verified+primary EmailAddress, password == email):
  1. A regular student.
  2. An educator who can reach the educator course-management interface
     (gated only by @login_required) and who owns a cohort registered for the
     published course, so the educator's cohort views show data. The educator is
     granted object-level view_cohort on that cohort.

COURSES (4, each with one viewable Topic so the player resolves):
  1. published-free    visibility=published,  access_config={"access_type":"free"}
  2. coming-soon       visibility=coming_soon
  3. hidden-course     visibility=hidden,  NO registration for the student
  4. hidden-registered visibility=hidden,  student IS registered (mid-course access)

RELATIONSHIPS:
  - Student registered in hidden-registered (and published-free) only; explicitly
    NOT registered in hidden-course (the command deletes any such row each run).
  - No CourseInterest rows are pre-created (the QA tester makes those via the UI).

All objects are created via site-aware factories with an explicit `site=`
override (the factories' thread-local site default is None outside a request).
"""

from typing import cast

import djclick as click
from allauth.account.models import EmailAddress
from guardian.shortcuts import assign_perm

from django.contrib.sites.models import Site

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import Course, CourseVisibility, Topic
from freedom_ls.student_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    UserCourseRegistrationFactory,
)
from freedom_ls.student_management.models import (
    Cohort,
    CohortCourseRegistration,
    UserCourseRegistration,
)

STUDENT_EMAIL = "demodev_visibility_student@email.com"
EDUCATOR_EMAIL = "demodev_visibility_educator@email.com"

COHORT_NAME = "QA Visibility Cohort"

PUBLISHED_FREE_TITLE = "QA Published Free Course (Visibility)"
PUBLISHED_FREE_SLUG = "qa-published-free-visibility"

COMING_SOON_TITLE = "QA Coming Soon Course (Visibility)"
COMING_SOON_SLUG = "qa-coming-soon-visibility"

HIDDEN_TITLE = "QA Hidden Course (Visibility)"
HIDDEN_SLUG = "qa-hidden-visibility"

HIDDEN_REGISTERED_TITLE = "QA Hidden Registered Course (Visibility)"
HIDDEN_REGISTERED_SLUG = "qa-hidden-registered-visibility"


def _get_or_create_user(
    site: Site, email: str, first_name: str, last_name: str
) -> User:
    """Create a login-ready user (password == email), or refresh the existing one."""
    existing: User | None = User.objects.filter(email=email).first()
    if existing is not None:
        existing.is_active = True
        existing.set_password(email)
        existing.save(update_fields=["is_active", "password"])
        return existing
    return cast(
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


def _ensure_verified_email(user: User) -> None:
    """Ensure a verified, primary EmailAddress exists (allauth login requires it)."""
    EmailAddress.objects.update_or_create(
        user=user,
        email=user.email,
        defaults={"verified": True, "primary": True},
    )


def _get_or_create_course(
    site: Site,
    *,
    title: str,
    slug: str,
    visibility: str,
    access_config: dict | None = None,
) -> Course:
    """Create a course with the given visibility/access_config and one viewable Topic.

    Idempotent: keyed on (slug, site). On re-run, refreshes visibility/access_config
    and guarantees at least one viewable Topic so /courses/<slug>/1/ resolves.
    """
    access_config = access_config if access_config is not None else {}
    course: Course | None = Course.objects.filter(slug=slug, site=site).first()
    if course is None:
        course = cast(
            Course,
            CourseFactory(
                title=title,
                slug=slug,
                visibility=visibility,
                access_config=access_config,
                site=site,
            ),
        )
    else:
        course.title = title
        course.visibility = visibility
        course.access_config = access_config
        course.save(update_fields=["title", "visibility", "access_config"])

    # Re-query so the children() memoization is fresh before counting viewables.
    if not Course.objects.get(pk=course.pk).viewable_items():
        topic = cast(
            Topic,
            TopicFactory(
                title=f"{title} - Intro Topic",
                content="# Welcome\n\nQA topic so the course player resolves.",
                site=site,
            ),
        )
        ContentCollectionItemFactory(
            collection_object=course, child_object=topic, site=site
        )
    return course


def _ensure_registration(site: Site, user: User, course: Course) -> None:
    """Ensure the student has an active registration for the course."""
    if not UserCourseRegistration.objects.filter(
        user=user, collection=course, site=site
    ).exists():
        UserCourseRegistrationFactory(
            user=user, collection=course, site=site, is_active=True
        )


@click.command()
@click.argument("site_name", default="DemoDev")
def command(site_name: str) -> None:
    """Create Course-Visibility (Coming Soon & Hidden) QA data.

    SITE_NAME is the site to create data on (default: DemoDev).
    """
    try:
        site = Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        available = list(Site.objects.values_list("name", flat=True))
        raise click.ClickException(
            f"Site '{site_name}' not found. Available: {available}"
        ) from e

    # --- Accounts -------------------------------------------------------
    student = _get_or_create_user(site, STUDENT_EMAIL, "DemoDev", "Visibility Student")
    _ensure_verified_email(student)

    educator = _get_or_create_user(
        site, EDUCATOR_EMAIL, "DemoDev", "Visibility Educator"
    )
    _ensure_verified_email(educator)

    # --- Courses --------------------------------------------------------
    published_free = _get_or_create_course(
        site,
        title=PUBLISHED_FREE_TITLE,
        slug=PUBLISHED_FREE_SLUG,
        visibility=CourseVisibility.PUBLISHED,
        access_config={"access_type": "free"},
    )
    coming_soon = _get_or_create_course(
        site,
        title=COMING_SOON_TITLE,
        slug=COMING_SOON_SLUG,
        visibility=CourseVisibility.COMING_SOON,
    )
    hidden = _get_or_create_course(
        site,
        title=HIDDEN_TITLE,
        slug=HIDDEN_SLUG,
        visibility=CourseVisibility.HIDDEN,
    )
    hidden_registered = _get_or_create_course(
        site,
        title=HIDDEN_REGISTERED_TITLE,
        slug=HIDDEN_REGISTERED_SLUG,
        visibility=CourseVisibility.HIDDEN,
    )

    # --- Student registrations -----------------------------------------
    # Registered in hidden-registered (mid-course access) and published-free.
    _ensure_registration(site, student, hidden_registered)
    _ensure_registration(site, student, published_free)
    # Guarantee the student is NOT registered in hidden-course.
    UserCourseRegistration.objects.filter(
        user=student, collection=hidden, site=site
    ).delete()

    # --- Educator cohort (so cohort views show data) -------------------
    cohort: Cohort | None = Cohort.objects.filter(name=COHORT_NAME, site=site).first()
    if cohort is None:
        cohort = cast(Cohort, CohortFactory(name=COHORT_NAME, site=site))
    assign_perm("view_cohort", educator, cohort)
    if not CohortCourseRegistration.objects.filter(
        cohort=cohort, collection=published_free, site=site
    ).exists():
        CohortCourseRegistrationFactory(
            cohort=cohort, collection=published_free, site=site, is_active=True
        )

    # --- Verification (fresh queries; children() is memoized per instance) ---
    student_regs = list(
        UserCourseRegistration.objects.filter(user=student, site=site)
        .select_related("collection")
        .values_list("collection__slug", flat=True)
    )

    click.secho("\n--- Course Visibility QA data ---", fg="cyan", bold=True)
    click.secho(f"Site: {site.name} (domain: {site.domain})", fg="cyan")
    click.secho(
        f"STUDENT  login: {student.email} / {student.email} (verified, active)",
        fg="green",
        bold=True,
    )
    click.secho(
        f"EDUCATOR login: {educator.email} / {educator.email} (verified, active)",
        fg="green",
        bold=True,
    )
    for label, course in [
        ("published-free   ", published_free),
        ("coming-soon      ", coming_soon),
        ("hidden-course    ", hidden),
        ("hidden-registered", hidden_registered),
    ]:
        fresh = Course.objects.get(pk=course.pk)
        click.secho(
            f"{label}: slug={fresh.slug}  visibility={fresh.visibility}  "
            f"access_config={fresh.access_config}  "
            f"viewable_items={len(fresh.viewable_items())}",
            fg="green",
        )
    click.secho(f"Educator cohort: {COHORT_NAME} (pk={cohort.pk})", fg="cyan")
    click.secho(
        f"Student registered in: {sorted(student_regs)}",
        fg="green",
    )
    not_in_hidden = not UserCourseRegistration.objects.filter(
        user=student, collection=hidden, site=site
    ).exists()
    click.secho(
        f"Student NOT registered in hidden-course: {not_in_hidden}",
        fg="green" if not_in_hidden else "red",
        bold=True,
    )
