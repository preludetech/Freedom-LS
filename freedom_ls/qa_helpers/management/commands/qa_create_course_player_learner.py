"""Create a login-ready learner for QA of the learner course player.

Creates (idempotently) a single learner who can log in via the browser and
exercises the three course-player redirect/resume cases:

1. Enrolled in a course WITH course parts but with NO progress, so the bare
   course URL resolves to item 1.
2. Enrolled in a second course WITH progress (last_accessed_item set a few
   items in) so the bare course URL resumes mid-course rather than at item 1.
3. NOT enrolled in a third existing course, so the bare course URL for that
   course redirects to its /preview/ page.

The login convention in this project is password == email address, so the
learner's password is set to its own email.
"""

from typing import cast

import djclick as click
from allauth.account.models import EmailAddress

from django.contrib.sites.models import Site
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import Course, Topic
from freedom_ls.form_engine.models import Form
from freedom_ls.learner_management.factories import LearnerCourseRegistrationFactory
from freedom_ls.learner_management.models import LearnerCourseRegistration
from freedom_ls.learner_progress.attempts import ensure_attempt
from freedom_ls.learner_progress.models import CourseProgress, TopicProgress
from freedom_ls.learner_progress.queries import course_progress_for
from freedom_ls.organisations.utils import get_default_organisation

LEARNER_EMAIL = "demodev_s1@email.com"

# Course used for each scenario. Slugs are validated against the site at runtime.
NO_PROGRESS_COURSE_SLUG = "functionality-demo-course-parts"
WITH_PROGRESS_COURSE_SLUG = "functionality-demo-show-end-with-topic"
NOT_ENROLLED_COURSE_SLUG = "functionality-demo-show-end-with-quiz"

# 1-based index in WITH_PROGRESS_COURSE.viewable_items() to resume at.
RESUME_INDEX = 3


def _get_course(site: Site, slug: str) -> Course:
    """Fetch a course on the given site or raise a helpful ClickException."""
    try:
        course: Course = Course.objects.get(slug=slug, site=site)
        return course
    except Course.DoesNotExist as e:
        available = list(
            Course.objects.filter(site=site).values_list("slug", flat=True)
        )
        raise click.ClickException(
            f"Course '{slug}' not found on site '{site.name}'. Available: {available}"
        ) from e


def _get_or_create_learner(site: Site) -> User:
    """Create the QA learner (password == email), or return the existing one."""
    existing: User | None = User.objects.filter(email=LEARNER_EMAIL).first()
    if existing is not None:
        # Ensure the existing account is usable for login.
        existing.is_active = True
        existing.set_password(LEARNER_EMAIL)
        existing.save(update_fields=["is_active", "password"])
        return existing
    return cast(
        User,
        UserFactory(
            email=LEARNER_EMAIL,
            first_name="DemoDev",
            last_name="Learner One",
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


def _register(user: User, course: Course, site: Site) -> None:
    """Register the user for the course (idempotent)."""
    if not LearnerCourseRegistration.objects.filter(
        learner__user=user, collection=course, site=site
    ).exists():
        LearnerCourseRegistrationFactory(
            learner__user=user,
            learner__organisation=get_default_organisation(site),
            collection=course,
            site=site,
        )


def _record_for(user: User, course: Course) -> CourseProgress:
    record = course_progress_for(user, course)
    if record is None:
        raise click.ClickException(
            f"No CourseProgress record for {user.email} on {course.slug}; "
            "register the learner before completing progress."
        )
    return record


def _set_resume_progress(
    user: User, course: Course, site: Site, resume_index: int
) -> None:
    """Give the user partial progress and point last_accessed_item at resume_index.

    Marks every viewable item before resume_index as complete and the item AT
    resume_index as started, so the course has >0% progress and the resume
    redirect lands on resume_index rather than item 1.
    """
    collection_items = course.viewable_collection_items()
    if not collection_items:
        raise click.ClickException(f"Course '{course.slug}' has no viewable items.")
    if resume_index > len(collection_items):
        raise click.ClickException(
            f"resume_index {resume_index} exceeds viewable item count "
            f"({len(collection_items)}) for '{course.slug}'."
        )

    record = _record_for(user, course)
    resume_collection_item = collection_items[resume_index - 1]
    resume_item = resume_collection_item.child

    # Complete every item before the resume point.
    for collection_item in collection_items[: resume_index - 1]:
        item = collection_item.child
        if isinstance(item, Topic):
            TopicProgress.objects.get_or_create(
                course_progress=record,
                collection_item=collection_item,
                defaults={
                    "topic": item,
                    "site": site,
                    "complete_time": timezone.now(),
                },
            )
        elif isinstance(item, Form):
            attempt = ensure_attempt(record, collection_item)
            if attempt.completed_time is None:
                attempt.completed_time = timezone.now()
                attempt.save(update_fields=["completed_time"])

    # Start (but do not complete) the resume item so it is genuinely "in progress".
    if isinstance(resume_item, Topic):
        TopicProgress.objects.get_or_create(
            course_progress=record,
            collection_item=resume_collection_item,
            defaults={"topic": resume_item, "site": site},
        )
    elif isinstance(resume_item, Form):
        ensure_attempt(record, resume_collection_item)

    completed = resume_index - 1
    percentage = round((completed / len(collection_items)) * 100)

    # Mirrors view_course_item's resume-pointer write: last_accessed_time is
    # written explicitly rather than by auto_now, and started_at is stamped
    # once, on first content access.
    now = timezone.now()
    record.progress_percentage = percentage
    record.last_accessed_item = resume_collection_item
    record.last_accessed_time = now
    if record.started_at is None:
        record.started_at = now
    record.save(
        update_fields=[
            "progress_percentage",
            "last_accessed_item",
            "last_accessed_time",
            "started_at",
        ]
    )


@click.command()
@click.argument("site_name", default="DemoDev")
def command(site_name: str) -> None:
    """Create a login-ready course-player QA learner.

    SITE_NAME is the site to create data on (default: DemoDev).
    """
    try:
        site = Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        available = list(Site.objects.values_list("name", flat=True))
        raise click.ClickException(
            f"Site '{site_name}' not found. Available: {available}"
        ) from e

    no_progress_course = _get_course(site, NO_PROGRESS_COURSE_SLUG)
    with_progress_course = _get_course(site, WITH_PROGRESS_COURSE_SLUG)
    not_enrolled_course = _get_course(site, NOT_ENROLLED_COURSE_SLUG)

    learner = _get_or_create_learner(site)
    _ensure_verified_email(learner)
    click.secho(
        f"Learner: {learner.email} (password: {learner.email}) "
        f"active={learner.is_active} site={site.name}",
        fg="green",
    )

    # Case 1: enrolled, no progress, course with parts.
    _register(learner, no_progress_course, site)
    # Defensively clear any stale progress so the bare URL really resolves to
    # item 1. Deleting the record is safe: the player self-heals it (with a
    # fresh created_at) via ensure_course_progress_record on the next visit.
    CourseProgress.objects.filter(
        learner__user=learner, course=no_progress_course, site=site
    ).delete()
    click.secho(
        f"Enrolled (NO progress): {no_progress_course.slug} "
        f"-> bare URL resolves to item 1",
        fg="green",
    )

    # Case 2: enrolled, with progress, resume mid-course.
    _register(learner, with_progress_course, site)
    _set_resume_progress(learner, with_progress_course, site, RESUME_INDEX)
    items = with_progress_course.viewable_items()
    resume_item = items[RESUME_INDEX - 1]
    click.secho(
        f"Enrolled (WITH progress): {with_progress_course.slug} "
        f"-> resumes to item {RESUME_INDEX} "
        f"({type(resume_item).__name__}: {resume_item.title})",
        fg="green",
    )

    # Case 3: NOT enrolled (report only; ensure no registration exists).
    # CourseProgress.learner_registration is PROTECT, so any record the
    # registration minted has to go first.
    CourseProgress.objects.filter(
        learner__user=learner, course=not_enrolled_course, site=site
    ).delete()
    LearnerCourseRegistration.objects.filter(
        learner__user=learner, collection=not_enrolled_course, site=site
    ).delete()
    click.secho(
        f"NOT enrolled: {not_enrolled_course.slug} "
        f"-> bare URL redirects to /courses/{not_enrolled_course.slug}/preview/",
        fg="green",
    )

    click.secho("\n--- Summary ---", fg="cyan", bold=True)
    click.secho(f"Site: {site.name} ({site.domain})", fg="cyan")
    click.secho(f"Login: {learner.email} / {learner.email}", fg="cyan", bold=True)
    click.secho(
        f"(a) enrolled, no progress, course-with-parts: {no_progress_course.slug}",
        fg="cyan",
    )
    click.secho(
        f"(b) enrolled, with progress, resumes item {RESUME_INDEX}: "
        f"{with_progress_course.slug}",
        fg="cyan",
    )
    click.secho(
        f"(c) NOT enrolled (redirects to preview): {not_enrolled_course.slug}",
        fg="cyan",
    )
