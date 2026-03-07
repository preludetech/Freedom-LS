"""Complete a form for students in a cohort (creates FormProgress records)."""

from datetime import timedelta

import djclick as click

from django.contrib.sites.models import Site
from django.utils import timezone

from freedom_ls.content_engine.models import Form
from freedom_ls.student_management.models import CohortMembership
from freedom_ls.student_progress.factories import FormProgressFactory
from freedom_ls.student_progress.models import FormProgress


@click.command()
@click.argument("site_name")
@click.option(
    "--cohort-name",
    required=True,
    help="Name of the cohort whose students will complete the form.",
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
    ).select_related("user")

    if not memberships.exists():
        raise click.ClickException(f"No students found in cohort '{cohort_name}'.")

    now = timezone.now()
    created_count = 0

    for i, membership in enumerate(memberships):
        user = membership.user
        if not FormProgress.objects.filter(form=form, user=user, site=site).exists():
            FormProgressFactory(
                form=form,
                user=user,
                site=site,
                completed_time=now - timedelta(hours=i),
                scores={
                    "Satisfaction": 5 + (i % 3),
                    "Recommendation": 3 + (i % 3),
                },
            )
            created_count += 1

    click.secho(
        f"Created {created_count} completions for form '{form.title}' "
        f"in cohort '{cohort_name}'",
        fg="green",
    )
