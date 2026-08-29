"""Seed item-scoped deadlines on a disposable ContentType so it can be half-nulled.

A "half-nulled" deadline row has ``content_type IS NULL`` while ``object_id``
stays populated. The deadline models declare ``on_delete=SET_NULL`` on
``content_type``, so deleting the ContentType row a deadline points at produces
exactly that state.

Deleting the ContentType a real course item uses is far too broad:
``ContentCollectionItem.child_type`` is ``on_delete=CASCADE``, so deleting the
Topic ContentType would delete every ContentCollectionItem whose child is a
topic -- i.e. strip every topic out of every course. This command instead scopes
one deadline on each of the three deadline models to an ``Activity`` that lives
outside every course, so the only collateral of deleting that ContentType is its
four (unheld) auth.Permission rows.
"""

from datetime import timedelta
from typing import cast

import djclick as click

from django.apps import apps
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType as DjangoContentType
from django.contrib.sites.models import Site
from django.db import models as django_models
from django.utils import timezone

from freedom_ls.content_engine.factories import ActivityFactory
from freedom_ls.content_engine.models import Activity
from freedom_ls.learner_management.factories import (
    CohortDeadlineFactory,
    LearnerCohortDeadlineOverrideFactory,
    LearnerDeadlineFactory,
)
from freedom_ls.learner_management.models import (
    CohortCourseRegistration,
    CohortDeadline,
    CohortMembership,
    Learner,
    LearnerCohortDeadlineOverride,
    LearnerCourseRegistration,
    LearnerDeadline,
)

TARGET_SLUG = "qa-half-nulled-deadline-target"
TARGET_TITLE = "QA Half-Nulled Deadline Target"


def _get_or_create_target(site: Site) -> Activity:
    """The out-of-course Activity every seeded deadline points at."""
    existing = Activity._base_manager.filter(site=site, slug=TARGET_SLUG).first()
    if existing is not None:
        return existing
    return cast(
        Activity, ActivityFactory(site=site, title=TARGET_TITLE, slug=TARGET_SLUG)
    )


def _describe_holders(content_type: DjangoContentType) -> list[str]:
    """Every row in the database whose FK points at ``content_type``."""
    lines: list[str] = []
    for model in apps.get_models():
        for field in model._meta.get_fields():
            if (
                isinstance(field, django_models.ForeignKey)
                and field.related_model is DjangoContentType
            ):
                count = model._base_manager.filter(**{field.name: content_type}).count()
                if count:
                    on_delete_fn = field.remote_field.on_delete
                    on_delete = (
                        on_delete_fn.__name__ if on_delete_fn is not None else "unknown"
                    )
                    lines.append(
                        f"{model._meta.label}.{field.name} "
                        f"on_delete={on_delete} -> {count} row(s)"
                    )
    return lines


@click.command()
@click.argument("site_name", default="DemoDev", required=False)
@click.option(
    "--cohort-name",
    default="QA Progress Demo Cohort",
    help="Cohort whose course registration carries the CohortDeadline.",
)
@click.option(
    "--course-slug",
    default="functionality-demo-course-parts",
    help="Course the registrations are for.",
)
@click.option(
    "--learner-email",
    default="demodev_s1@email.com",
    help="Learner whose individual registration carries the LearnerDeadline.",
)
@click.option(
    "--override-email",
    default="qa-eve.middle@example.com",
    help="Cohort member who carries the LearnerCohortDeadlineOverride.",
)
@click.option(
    "--days-from-now",
    default=30,
    type=int,
    help="Deadline N days from now (default: 30, i.e. future and harmless).",
)
@click.option(
    "--delete-content-type",
    is_flag=True,
    default=False,
    help="Also delete the target ContentType, half-nulling the seeded rows.",
)
def command(
    site_name: str,
    cohort_name: str,
    course_slug: str,
    learner_email: str,
    override_email: str,
    days_from_now: int,
    delete_content_type: bool,
) -> None:
    try:
        site = Site.objects.get(name=site_name)
    except Site.DoesNotExist as exc:
        raise click.ClickException(f"Site '{site_name}' not found.") from exc

    target = _get_or_create_target(site)
    click.secho(f"Target content item: {target} (pk={target.pk})", fg="cyan")

    # Check for the finished state BEFORE touching get_for_model(), which is a
    # get_or_create and would silently resurrect the ContentType this command
    # exists to delete.
    already = {
        model.__name__: model._base_manager.filter(
            content_type__isnull=True, object_id=target.pk
        ).first()
        for model in (CohortDeadline, LearnerDeadline, LearnerCohortDeadlineOverride)
    }
    settled = {name: row for name, row in already.items() if row is not None}
    if len(settled) == len(already):
        click.secho(
            "Already half-nulled -- nothing to do (re-seeding would resurrect the "
            "ContentType). Existing rows:",
            fg="green",
        )
        for name, row in settled.items():
            click.secho(
                f"  {name} pk={row.pk} content_type=None object_id={row.object_id}",
                fg="green",
            )
        return

    content_type = DjangoContentType.objects.get_for_model(Activity)
    click.secho(
        f"ContentType id={content_type.id} "
        f"{content_type.app_label}.{content_type.model}",
        fg="cyan",
    )

    try:
        cohort_registration = CohortCourseRegistration.objects.select_related(
            "cohort", "course"
        ).get(cohort__name=cohort_name, course__slug=course_slug, site=site)
    except CohortCourseRegistration.DoesNotExist as exc:
        raise click.ClickException(
            f"No cohort course registration for '{cohort_name}' / '{course_slug}'."
        ) from exc

    try:
        learner_registration = LearnerCourseRegistration.objects.select_related(
            "learner__user", "course"
        ).get(learner__user__email=learner_email, course__slug=course_slug, site=site)
    except LearnerCourseRegistration.DoesNotExist as exc:
        raise click.ClickException(
            f"No individual registration for '{learner_email}' / '{course_slug}'."
        ) from exc

    override_learner = Learner.objects.filter(
        user__email=override_email,
        organisation=cohort_registration.cohort.organisation,
        site=site,
    ).first()
    if override_learner is None:
        raise click.ClickException(
            f"No Learner for '{override_email}' in "
            f"'{cohort_registration.cohort.organisation}'."
        )
    if not CohortMembership.objects.filter(
        learner=override_learner, cohort=cohort_registration.cohort
    ).exists():
        raise click.ClickException(
            f"'{override_email}' is not a member of '{cohort_name}'; "
            "LearnerCohortDeadlineOverride.clean() forbids the override."
        )

    deadline = timezone.now() + timedelta(days=days_from_now)
    common = {
        "content_type": content_type,
        "object_id": target.pk,
        "site": site,
    }

    cohort_deadline = CohortDeadline.objects.filter(
        cohort_course_registration=cohort_registration, **common
    ).first()
    if cohort_deadline is None:
        cohort_deadline = cast(
            CohortDeadline,
            CohortDeadlineFactory(
                cohort_course_registration=cohort_registration,
                content_item=target,
                deadline=deadline,
                is_hard_deadline=False,
                site=site,
            ),
        )

    learner_deadline = LearnerDeadline.objects.filter(
        learner_course_registration=learner_registration, **common
    ).first()
    if learner_deadline is None:
        learner_deadline = cast(
            LearnerDeadline,
            LearnerDeadlineFactory(
                learner_course_registration=learner_registration,
                content_item=target,
                deadline=deadline,
                is_hard_deadline=False,
                site=site,
            ),
        )

    override = LearnerCohortDeadlineOverride.objects.filter(
        cohort_course_registration=cohort_registration,
        learner=override_learner,
        **common,
    ).first()
    if override is None:
        override = cast(
            LearnerCohortDeadlineOverride,
            LearnerCohortDeadlineOverrideFactory(
                cohort_course_registration=cohort_registration,
                learner=override_learner,
                content_item=target,
                deadline=deadline,
                is_hard_deadline=False,
                site=site,
            ),
        )

    for row in (cohort_deadline, learner_deadline, override):
        click.secho(
            f"{type(row).__name__} pk={row.pk} object_id={row.object_id} :: {row}",
            fg="green",
        )

    if not delete_content_type:
        click.secho(
            "\nContentType left in place. Re-run with --delete-content-type "
            "to half-null these rows.",
            fg="yellow",
        )
        return

    click.secho(
        f"\nAbout to delete ContentType id={content_type.id} "
        f"{content_type.app_label}.{content_type.model}. Rows pointing at it:",
        fg="yellow",
    )
    for line in _describe_holders(content_type):
        click.secho(f"  {line}", fg="yellow")

    held = Permission.objects.filter(content_type=content_type).filter(
        django_models.Q(user__isnull=False) | django_models.Q(group__isnull=False)
    )
    if held.exists():
        raise click.ClickException(
            "Refusing to delete: its permissions are held by "
            f"{sorted(set(held.values_list('codename', flat=True)))}."
        )

    total, per_model = content_type.delete()
    click.secho(f"Deleted {total} row(s): {per_model}", fg="red")

    for model, pk in (
        (CohortDeadline, cohort_deadline.pk),
        (LearnerDeadline, learner_deadline.pk),
        (LearnerCohortDeadlineOverride, override.pk),
    ):
        refreshed = model._base_manager.filter(pk=pk).first()
        if refreshed is None:
            click.secho(f"{model.__name__} pk={pk} WAS CASCADED AWAY", fg="red")
            continue
        click.secho(
            f"{model.__name__} pk={refreshed.pk} "
            f"content_type={refreshed.content_type_id} "
            f"object_id={refreshed.object_id}",
            fg="green",
        )
