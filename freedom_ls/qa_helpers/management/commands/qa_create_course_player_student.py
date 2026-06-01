"""Create a login-ready student for QA of the student course player.

Creates (idempotently) a single student who can log in via the browser and
exercises the three course-player redirect/resume cases:

1. Enrolled in a course WITH course parts but with NO progress, so the bare
   course URL resolves to item 1.
2. Enrolled in a second course WITH progress (last_accessed_item set a few
   items in) so the bare course URL resumes mid-course rather than at item 1.
3. NOT enrolled in a third existing course, so the bare course URL for that
   course redirects to its /preview/ page.

The login convention in this project is password == email address, so the
student's password is set to its own email.
"""

from typing import cast

import djclick as click
from allauth.account.models import EmailAddress

from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import Course, Form, Topic
from freedom_ls.student_management.factories import UserCourseRegistrationFactory
from freedom_ls.student_management.models import UserCourseRegistration
from freedom_ls.student_progress.factories import (
    CourseProgressFactory,
    FormProgressFactory,
    TopicProgressFactory,
)
from freedom_ls.student_progress.models import (
    CourseProgress,
    FormProgress,
    TopicProgress,
)

STUDENT_EMAIL = "demodev_s1@email.com"

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


def _get_or_create_student(site: Site) -> User:
    """Create the QA student (password == email), or return the existing one."""
    existing: User | None = User.objects.filter(email=STUDENT_EMAIL).first()
    if existing is not None:
        # Ensure the existing account is usable for login.
        existing.is_active = True
        existing.set_password(STUDENT_EMAIL)
        existing.save(update_fields=["is_active", "password"])
        return existing
    return cast(
        User,
        UserFactory(
            email=STUDENT_EMAIL,
            first_name="DemoDev",
            last_name="Student One",
            is_active=True,
            password=STUDENT_EMAIL,
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
    if not UserCourseRegistration.objects.filter(
        user=user, collection=course, site=site
    ).exists():
        UserCourseRegistrationFactory(user=user, collection=course, site=site)


def _set_resume_progress(
    user: User, course: Course, site: Site, resume_index: int
) -> None:
    """Give the user partial progress and point last_accessed_item at resume_index.

    Marks every viewable item before resume_index as complete and the item AT
    resume_index as started, so the course has >0% progress and the resume
    redirect lands on resume_index rather than item 1.
    """
    items = course.viewable_items()
    if not items:
        raise click.ClickException(f"Course '{course.slug}' has no viewable items.")
    if resume_index > len(items):
        raise click.ClickException(
            f"resume_index {resume_index} exceeds viewable item count "
            f"({len(items)}) for '{course.slug}'."
        )

    resume_item = items[resume_index - 1]

    # Complete every item before the resume point.
    for item in items[: resume_index - 1]:
        if isinstance(item, Topic):
            TopicProgress.objects.get_or_create(
                user=user,
                topic=item,
                site=site,
                defaults={"complete_time": timezone.now()},
            )
        elif isinstance(item, Form):
            FormProgress.objects.get_or_create(
                user=user,
                form=item,
                site=site,
                defaults={"completed_time": timezone.now()},
            )

    # Start (but do not complete) the resume item so it is genuinely "in progress".
    if (
        isinstance(resume_item, Topic)
        and not TopicProgress.objects.filter(
            user=user, topic=resume_item, site=site
        ).exists()
    ):
        TopicProgressFactory(user=user, topic=resume_item, site=site)
    elif (
        isinstance(resume_item, Form)
        and not FormProgress.objects.filter(
            user=user, form=resume_item, site=site
        ).exists()
    ):
        FormProgressFactory(user=user, form=resume_item, site=site)

    completed = resume_index - 1
    percentage = round((completed / len(items)) * 100)

    # update_course_progress_on_completion does not set site, so create/own the
    # CourseProgress row directly with site and the resume pointer.
    ct = ContentType.objects.get_for_model(type(resume_item))
    progress: CourseProgress | None = CourseProgress.objects.filter(
        user=user, course=course, site=site
    ).first()
    if progress is None:
        progress = cast(
            CourseProgress,
            CourseProgressFactory(user=user, course=course, site=site),
        )
    progress.progress_percentage = percentage
    progress.last_accessed_content_type = ct
    progress.last_accessed_object_id = resume_item.pk
    progress.save(
        update_fields=[
            "progress_percentage",
            "last_accessed_content_type",
            "last_accessed_object_id",
        ]
    )


@click.command()
@click.argument("site_name", default="DemoDev")
def command(site_name: str) -> None:
    """Create a login-ready course-player QA student.

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

    student = _get_or_create_student(site)
    _ensure_verified_email(student)
    click.secho(
        f"Student: {student.email} (password: {student.email}) "
        f"active={student.is_active} site={site.name}",
        fg="green",
    )

    # Case 1: enrolled, no progress, course with parts.
    _register(student, no_progress_course, site)
    # Defensively clear any stale progress so the bare URL really resolves to item 1.
    CourseProgress.objects.filter(
        user=student, course=no_progress_course, site=site
    ).delete()
    click.secho(
        f"Enrolled (NO progress): {no_progress_course.slug} "
        f"-> bare URL resolves to item 1",
        fg="green",
    )

    # Case 2: enrolled, with progress, resume mid-course.
    _register(student, with_progress_course, site)
    _set_resume_progress(student, with_progress_course, site, RESUME_INDEX)
    items = with_progress_course.viewable_items()
    resume_item = items[RESUME_INDEX - 1]
    click.secho(
        f"Enrolled (WITH progress): {with_progress_course.slug} "
        f"-> resumes to item {RESUME_INDEX} "
        f"({type(resume_item).__name__}: {resume_item.title})",
        fg="green",
    )

    # Case 3: NOT enrolled (report only; ensure no registration exists).
    UserCourseRegistration.objects.filter(
        user=student, collection=not_enrolled_course, site=site
    ).delete()
    click.secho(
        f"NOT enrolled: {not_enrolled_course.slug} "
        f"-> bare URL redirects to /courses/{not_enrolled_course.slug}/preview/",
        fg="green",
    )

    click.secho("\n--- Summary ---", fg="cyan", bold=True)
    click.secho(f"Site: {site.name} ({site.domain})", fg="cyan")
    click.secho(f"Login: {student.email} / {student.email}", fg="cyan", bold=True)
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
