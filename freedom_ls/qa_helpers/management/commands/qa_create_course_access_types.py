"""Create QA data for the "Course Access Types - Free & Application-Gated" feature.

Creates (idempotently) on a single site (default: DemoDev):

1. A login-ready learner enrolled in NOTHING:
   - verified, primary EmailAddress (allauth mandatory verification),
   - ZERO UserCourseRegistration rows,
   - ZERO CourseApplication rows.
   - Login convention in this project is password == email.

2. A FREE course (access_config = {"access_type": "free"}) with one viewable Topic
   so the TOC and item URL (/courses/<slug>/1/) resolve.

3. An APPLICATION-GATED course (access_config = {"access_type": "application_gated"})
   with one viewable Topic, and with NO CourseApplication for the learner above so
   the first-time "Apply now" flow can be exercised.

All objects are created with site-aware factories and the explicit `site=` override
(the factories' thread-local site default is None outside a request).
"""

from typing import cast

import djclick as click
from allauth.account.models import EmailAddress

from django.contrib.sites.models import Site

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import Course, Topic
from freedom_ls.course_applications.models import CourseApplication
from freedom_ls.student_management.models import UserCourseRegistration

LEARNER_EMAIL = "demodev_access_learner@email.com"

FREE_COURSE_TITLE = "QA Free Course (Access Types)"
FREE_COURSE_SLUG = "qa-free-course-access-types"

GATED_COURSE_TITLE = "QA Application-Gated Course (Access Types)"
GATED_COURSE_SLUG = "qa-application-gated-course-access-types"


def _get_or_create_learner(site: Site) -> User:
    """Create the QA learner (password == email), or return the existing one."""
    existing: User | None = User.objects.filter(email=LEARNER_EMAIL).first()
    if existing is not None:
        existing.is_active = True
        existing.set_password(LEARNER_EMAIL)
        existing.save(update_fields=["is_active", "password"])
        return existing
    return cast(
        User,
        UserFactory(
            email=LEARNER_EMAIL,
            first_name="DemoDev",
            last_name="Access Learner",
            is_active=True,
            password=LEARNER_EMAIL,
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
    site: Site, *, title: str, slug: str, access_config: dict
) -> Course:
    """Create a course with the given access_config and one viewable Topic.

    Idempotent: keyed on (slug, site). On re-run, refreshes access_config and
    guarantees at least one viewable Topic exists.
    """
    course: Course | None = Course.objects.filter(slug=slug, site=site).first()
    if course is None:
        course = cast(
            Course,
            CourseFactory(
                title=title,
                slug=slug,
                access_config=access_config,
                site=site,
            ),
        )
    else:
        course.title = title
        course.access_config = access_config
        course.save(update_fields=["title", "access_config"])

    if not course.viewable_items():
        topic = cast(
            Topic,
            TopicFactory(
                title=f"{title} - Intro Topic",
                content="# Welcome\n\nThis is a QA topic so the course player resolves.",
                site=site,
            ),
        )
        ContentCollectionItemFactory(
            collection_object=course, child_object=topic, site=site
        )
    return course


@click.command()
@click.argument("site_name", default="DemoDev")
def command(site_name: str) -> None:
    """Create Course-Access-Types QA data.

    SITE_NAME is the site to create data on (default: DemoDev).
    """
    try:
        site = Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        available = list(Site.objects.values_list("name", flat=True))
        raise click.ClickException(
            f"Site '{site_name}' not found. Available: {available}"
        ) from e

    learner = _get_or_create_learner(site)
    _ensure_verified_email(learner)

    free_course = _get_or_create_course(
        site,
        title=FREE_COURSE_TITLE,
        slug=FREE_COURSE_SLUG,
        access_config={"access_type": "free"},
    )
    gated_course = _get_or_create_course(
        site,
        title=GATED_COURSE_TITLE,
        slug=GATED_COURSE_SLUG,
        access_config={"access_type": "application_gated"},
    )

    # Guarantee the "enrolled in NOTHING" and "no application yet" preconditions.
    UserCourseRegistration.objects.filter(user=learner, site=site).delete()
    CourseApplication.objects.filter(user=learner, site=site).delete()

    reg_count = UserCourseRegistration.objects.filter(user=learner, site=site).count()
    app_count = CourseApplication.objects.filter(user=learner, site=site).count()

    click.secho("\n--- Course Access Types QA data ---", fg="cyan", bold=True)
    click.secho(f"Site: {site.name} (domain: {site.domain})", fg="cyan")
    click.secho(
        f"Learner login: {learner.email} / {learner.email} "
        f"(verified, active={learner.is_active})",
        fg="green",
        bold=True,
    )
    click.secho(
        f"FREE course:  '{free_course.title}'  slug={free_course.slug}  "
        f"access_config={free_course.access_config}  "
        f"viewable_items={len(free_course.viewable_items())}",
        fg="green",
    )
    click.secho(
        f"GATED course: '{gated_course.title}'  slug={gated_course.slug}  "
        f"access_config={gated_course.access_config}  "
        f"viewable_items={len(gated_course.viewable_items())}",
        fg="green",
    )
    click.secho(
        f"Learner registrations: {reg_count} | Learner applications: {app_count}",
        fg="green" if reg_count == 0 and app_count == 0 else "red",
        bold=True,
    )
