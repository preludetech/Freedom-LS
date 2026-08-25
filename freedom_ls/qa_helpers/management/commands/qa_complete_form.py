"""Complete a form for learners in a cohort (creates FormProgress records)."""

from datetime import timedelta
from typing import cast

import djclick as click

from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.utils import timezone

from freedom_ls.content_engine.models import ContentCollectionItem, Course
from freedom_ls.form_engine.models import Form, FormProgress
from freedom_ls.learner_management.models import CohortMembership
from freedom_ls.learner_progress.factories import CourseFormAttemptFactory
from freedom_ls.learner_progress.models import CourseFormAttempt
from freedom_ls.learner_progress.queries import course_progress_for


def _course_placing(form: Form, site: Site) -> tuple[Course, ContentCollectionItem]:
    """The course `form` is placed in, and the form's own placement.

    Follows one level of CoursePart nesting: a form placed inside a part is
    still "in" the course that places the part.
    """
    item = (
        ContentCollectionItem.objects.filter(
            child_type=ContentType.objects.get_for_model(Form),
            child_id=form.pk,
            site=site,
        )
        .select_related("collection_type")
        .first()
    )
    if item is None:
        raise click.ClickException(
            f"Form '{form.slug}' is not placed in any course on site '{site.name}'."
        )
    if isinstance(item.collection, Course):
        return cast(Course, item.collection), item

    part = item.collection
    parent = (
        ContentCollectionItem.objects.filter(
            child_type=ContentType.objects.get_for_model(type(part)),
            child_id=part.pk,
            site=site,
        )
        .select_related("collection_type")
        .first()
    )
    if parent is None or not isinstance(parent.collection, Course):
        raise click.ClickException(
            f"Form '{form.slug}' is nested too deeply to resolve its course."
        )
    return cast(Course, parent.collection), item


@click.command()
@click.argument("site_name")
@click.option(
    "--cohort-name",
    required=True,
    help="Name of the cohort whose learners will complete the form.",
)
@click.option(
    "--form-slug",
    required=True,
    help="Slug of the form to complete.",
)
def command(
    site_name: str,
    cohort_name: str,
    form_slug: str,
) -> None:
    try:
        site = Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        raise click.ClickException(f"Site with name '{site_name}' not found.") from e

    try:
        form = Form.objects.get(slug=form_slug, site=site)
    except Form.DoesNotExist as e:
        raise click.ClickException(f"Form with slug '{form_slug}' not found.") from e

    memberships = CohortMembership.objects.filter(
        cohort__name=cohort_name,
        site=site,
    ).select_related("learner__user")

    if not memberships.exists():
        raise click.ClickException(f"No learners found in cohort '{cohort_name}'.")

    course, collection_item = _course_placing(form, site)

    now = timezone.now()
    created_count = 0
    skipped_count = 0

    for i, membership in enumerate(memberships):
        user = membership.learner.user
        record = course_progress_for(user, course)
        if record is None:
            # Not registered for the course this form is placed in -- nothing
            # to hang an attempt off.
            skipped_count += 1
            continue
        if not CourseFormAttempt.objects.filter(
            course_progress=record, form_progress__form=form
        ).exists():
            attempt = cast(
                "CourseFormAttempt",
                CourseFormAttemptFactory(
                    course_progress=record,
                    form=form,
                    collection_item=collection_item,
                    site=site,
                ),
            )
            # Score through complete(), so the scores dict comes out in the shape
            # the form's own strategy writes. A hand-rolled dict here seeds data
            # no real attempt could produce, which readers then have to survive.
            # complete() early-returns once completed_time is set, so the
            # staggered timestamp is stamped after it, not passed in.
            progress: FormProgress = attempt.form_progress
            progress.complete()
            progress.completed_time = now - timedelta(hours=i)
            progress.save()
            created_count += 1

    if skipped_count:
        click.secho(
            f"Skipped {skipped_count} learner(s) not registered for '{course.slug}'.",
            fg="yellow",
        )
    click.secho(
        f"Created {created_count} completions for form '{form.title}' "
        f"in cohort '{cohort_name}'",
        fg="green",
    )
