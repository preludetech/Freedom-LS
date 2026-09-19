"""Seed QA data for the google-analytics-setup frontend QA plan (section 0.2).

Idempotent. Assumes ``create_demo_data`` and
``content_save demo_content <SITE_NAME>`` have already been run.

Creates / resets on SITE_NAME (default DemoDev):

1. Learner A (``qa-learner-a@email.com``): registered for a short, form-free
   demo course, with its CourseProgress reset to a freshly-registered state
   (started_at / completed_time etc. null) and no TopicProgress for it.
2. Learner B (``qa-learner-b@email.com``): no CourseApplication rows.
3. An application-gated course with NO application form and one topic.

Both learners are non-staff, have a verified primary email, and their
password equals their email.
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
from freedom_ls.content_engine.models import Course
from freedom_ls.course_applications.models import CourseApplication
from freedom_ls.learner_management.factories import LearnerCourseRegistrationFactory
from freedom_ls.learner_management.models import LearnerCourseRegistration
from freedom_ls.learner_progress.models import TopicProgress
from freedom_ls.learner_progress.queries import course_progress_for
from freedom_ls.organisations.utils import get_default_organisation

LEARNER_A_EMAIL = "qa-learner-a@email.com"
LEARNER_B_EMAIL = "qa-learner-b@email.com"

# Three topics, no forms: quick to "Next" through to "Finish Course".
LEARNER_A_COURSE_SLUG = "standard-markdown-demo-finance"

NO_FORM_GATED_TITLE = "QA Application-Gated Course (No Form)"
NO_FORM_GATED_SLUG = "qa-application-gated-course-no-form"


def _get_or_create_learner(site: Site, email: str, last_name: str) -> User:
    user: User | None = User.objects.filter(email=email).first()
    if user is None:
        user = cast(
            User,
            UserFactory(
                email=email,
                first_name="QA",
                last_name=last_name,
                password=email,
                site=site,
            ),
        )
    else:
        user.is_active = True
        user.is_staff = False
        user.is_superuser = False
        user.set_password(email)
        user.save(update_fields=["is_active", "is_staff", "is_superuser", "password"])
    EmailAddress.objects.update_or_create(
        user=user, email=user.email, defaults={"verified": True, "primary": True}
    )
    return user


def _get_course(site: Site, slug: str) -> Course:
    course: Course | None = Course.objects.filter(slug=slug, site=site).first()
    if course is None:
        raise click.ClickException(
            f"Course '{slug}' not found on '{site.name}'. Run content_save first."
        )
    return course


def _get_or_create_no_form_gated_course(site: Site) -> Course:
    course: Course | None = Course.objects.filter(
        slug=NO_FORM_GATED_SLUG, site=site
    ).first()
    access_config = {"access_type": "application_gated"}
    if course is None:
        course = cast(
            Course,
            CourseFactory(
                title=NO_FORM_GATED_TITLE,
                slug=NO_FORM_GATED_SLUG,
                access_config=access_config,
                site=site,
            ),
        )
    elif course.access_config != access_config:
        course.access_config = access_config
        course.save(update_fields=["access_config"])
    if not course.viewable_items():
        topic = TopicFactory(
            title=f"{NO_FORM_GATED_TITLE} - Intro",
            content="# Welcome\n\nQA topic for the no-form application-gated course.",
            site=site,
        )
        ContentCollectionItemFactory(
            collection_object=course, child_object=topic, site=site
        )
    return course


@click.command()
@click.argument("site_name", default="DemoDev")
def command(site_name: str) -> None:
    """Create the GA-setup QA seed on SITE_NAME (default: DemoDev)."""
    site = Site.objects.filter(name=site_name).first()
    if site is None:
        raise click.ClickException(f"Site '{site_name}' not found.")

    # Learner A: registered, freshly-registered progress, no topic progress.
    learner_a = _get_or_create_learner(site, LEARNER_A_EMAIL, "Learner A")
    course_a = _get_course(site, LEARNER_A_COURSE_SLUG)
    if not LearnerCourseRegistration.objects.filter(
        learner__user=learner_a, course=course_a, site=site, is_active=True
    ).exists():
        LearnerCourseRegistrationFactory(
            learner__user=learner_a,
            learner__organisation=get_default_organisation(site),
            course=course_a,
            site=site,
        )
    record = course_progress_for(learner_a, course_a)
    if record is None:
        raise click.ClickException("Learner A has no CourseProgress record.")
    deleted = TopicProgress.objects.filter(course_progress=record).delete()
    record.started_at = None
    record.completed_time = None
    record.last_accessed_item = None
    record.last_accessed_time = None
    record.progress_percentage = 0
    record.save(
        update_fields=[
            "started_at",
            "completed_time",
            "last_accessed_item",
            "last_accessed_time",
            "progress_percentage",
        ]
    )

    # Learner B: no applications.
    learner_b = _get_or_create_learner(site, LEARNER_B_EMAIL, "Learner B")
    apps_deleted = CourseApplication.objects.filter(user=learner_b).delete()

    gated_no_form = _get_or_create_no_form_gated_course(site)

    click.secho(f"Site: {site.name} ({site.domain})", fg="cyan")
    click.secho(
        f"Learner A pk={learner_a.pk} {learner_a.email}: course "
        f"'{course_a.title}' slug={course_a.slug} "
        f"items={len(course_a.viewable_items())}; CourseProgress pk={record.pk} "
        f"reset; TopicProgress deleted={deleted}",
        fg="green",
    )
    click.secho(
        f"Learner B pk={learner_b.pk} {learner_b.email}: "
        f"CourseApplications deleted={apps_deleted}",
        fg="green",
    )
    click.secho(
        f"No-form gated course: '{gated_no_form.title}' slug={gated_no_form.slug} "
        f"access_config={gated_no_form.access_config}",
        fg="green",
    )
