"""Create student deadline overrides for QA testing."""

import djclick as click
from django.contrib.contenttypes.models import ContentType as DjangoContentType
from django.contrib.sites.models import Site
from django.utils import timezone

from freedom_ls.content_engine.models import Form, Topic
from freedom_ls.student_management.models import (
    CohortCourseRegistration,
    CohortMembership,
    StudentCohortDeadlineOverride,
)


@click.command()
@click.argument("site_name")
@click.option("--cohort-name", required=True, help="Name of the cohort")
@click.option("--course-slug", required=True, help="Slug of the course")
@click.option(
    "--student-email",
    required=True,
    help="Email of the student to give the override to",
)
@click.option(
    "--item-slug",
    default=None,
    help="Slug of a specific topic or form. If omitted, creates a course-level override.",
)
@click.option(
    "--days-from-now",
    default=30,
    type=int,
    help="Deadline N days from now. Use negative for past dates. (default: 30)",
)
@click.option(
    "--soft",
    is_flag=True,
    default=False,
    help="Make this a soft deadline (default is hard)",
)
def command(
    site_name: str,
    cohort_name: str,
    course_slug: str,
    student_email: str,
    item_slug: str | None,
    days_from_now: int,
    soft: bool,
) -> None:
    from freedom_ls.content_engine.models import Course  # noqa: F811

    try:
        site = Site.objects.get(name=site_name)
    except Site.DoesNotExist:
        raise click.ClickException(f"Site with name '{site_name}' not found.")

    try:
        registration = CohortCourseRegistration.objects.select_related(
            "cohort", "collection"
        ).get(
            cohort__name=cohort_name,
            collection__slug=course_slug,
            site=site,
        )
    except CohortCourseRegistration.DoesNotExist:
        raise click.ClickException(
            f"No course registration found for cohort '{cohort_name}' and course '{course_slug}'."
        )

    try:
        membership = CohortMembership.objects.select_related("student__user").get(
            cohort=registration.cohort,
            student__user__email=student_email,
            site=site,
        )
    except CohortMembership.DoesNotExist:
        raise click.ClickException(
            f"Student '{student_email}' is not a member of cohort '{cohort_name}'."
        )

    student = membership.student
    is_hard = not soft
    deadline = timezone.now() + timezone.timedelta(days=days_from_now)

    content_type = None
    object_id = None

    if item_slug:
        topic = Topic.objects.filter(slug=item_slug, site=site).first()
        form = Form.objects.filter(slug=item_slug, site=site).first()

        if topic:
            content_type = DjangoContentType.objects.get_for_model(Topic)
            object_id = topic.id
            item_name = topic.title
        elif form:
            content_type = DjangoContentType.objects.get_for_model(Form)
            object_id = form.id
            item_name = form.title
        else:
            raise click.ClickException(f"No topic or form found with slug '{item_slug}'.")
    else:
        item_name = "course-level"

    override, created = StudentCohortDeadlineOverride.objects.get_or_create(
        cohort_course_registration=registration,
        student=student,
        content_type=content_type,
        object_id=object_id,
        site=site,
        defaults={
            "deadline": deadline,
            "is_hard_deadline": is_hard,
        },
    )

    if created:
        deadline_type = "hard" if is_hard else "soft"
        click.secho(
            f"Created {deadline_type} deadline override for '{student_email}' "
            f"on {item_name}: {deadline.strftime('%Y-%m-%d %H:%M')}",
            fg="green",
        )
    else:
        click.secho(
            f"Override already exists for '{student_email}' on {item_name}. "
            f"Current deadline: {override.deadline.strftime('%Y-%m-%d %H:%M')}",
            fg="yellow",
        )
