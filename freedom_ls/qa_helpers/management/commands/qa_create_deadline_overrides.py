"""Create student deadline overrides for QA testing."""

from datetime import timedelta

import djclick as click

from django.contrib.sites.models import Site
from django.utils import timezone

from freedom_ls.content_engine.models import Form, Topic
from freedom_ls.student_management.factories import UserCohortDeadlineOverrideFactory
from freedom_ls.student_management.models import (
    CohortCourseRegistration,
    CohortMembership,
    UserCohortDeadlineOverride,
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
    try:
        site = Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        raise click.ClickException(f"Site with name '{site_name}' not found.") from e

    try:
        registration = CohortCourseRegistration.objects.select_related(
            "cohort", "collection"
        ).get(
            cohort__name=cohort_name,
            collection__slug=course_slug,
            site=site,
        )
    except CohortCourseRegistration.DoesNotExist as e:
        raise click.ClickException(
            f"No course registration found for cohort '{cohort_name}' and course '{course_slug}'."
        ) from e

    try:
        membership = CohortMembership.objects.select_related("user").get(
            cohort=registration.cohort,
            user__email=student_email,
            site=site,
        )
    except CohortMembership.DoesNotExist as e:
        raise click.ClickException(
            f"Student '{student_email}' is not a member of cohort '{cohort_name}'."
        ) from e

    user = membership.user
    is_hard = not soft
    deadline = timezone.now() + timedelta(days=days_from_now)

    content_item = None
    item_name = "course-level"

    if item_slug:
        topic = Topic.objects.filter(slug=item_slug, site=site).first()
        form = Form.objects.filter(slug=item_slug, site=site).first()

        if topic:
            content_item = topic
            item_name = topic.title
        elif form:
            content_item = form
            item_name = form.title
        else:
            raise click.ClickException(
                f"No topic or form found with slug '{item_slug}'."
            )

    # Check for existing override using the unique constraint fields
    lookup = {
        "cohort_course_registration": registration,
        "user": user,
        "content_type": None,
        "object_id": None,
        "site": site,
    }
    if content_item:
        from django.contrib.contenttypes.models import ContentType as DjangoContentType

        lookup["content_type"] = DjangoContentType.objects.get_for_model(content_item)
        lookup["object_id"] = content_item.pk

    try:
        override = UserCohortDeadlineOverride.objects.get(**lookup)
        click.secho(
            f"Override already exists for '{student_email}' on {item_name}. "
            f"Current deadline: {override.deadline.strftime('%Y-%m-%d %H:%M')}",
            fg="yellow",
        )
    except UserCohortDeadlineOverride.DoesNotExist:
        factory_kwargs = {
            "cohort_course_registration": registration,
            "user": user,
            "deadline": deadline,
            "is_hard_deadline": is_hard,
            "site": site,
        }
        if content_item:
            factory_kwargs["content_item"] = content_item
        UserCohortDeadlineOverrideFactory(**factory_kwargs)

        deadline_type = "hard" if is_hard else "soft"
        click.secho(
            f"Created {deadline_type} deadline override for '{student_email}' "
            f"on {item_name}: {deadline.strftime('%Y-%m-%d %H:%M')}",
            fg="green",
        )
