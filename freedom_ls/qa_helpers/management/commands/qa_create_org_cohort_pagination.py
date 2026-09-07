"""Pad one organisation with enough cohorts to page its admin Cohorts tab.

``OrganisationCohortInline`` (``freedom_ls/learner_management/admin.py``) hands
its queryset to a Paginator at ``per_page = 20``, ordered by ``name``. The
browser check the QA plan asks for -- page through the tab and confirm no row
repeats and none is skipped across a page boundary -- needs at least three
pages, and the largest organisation in the dev database has only 16 cohorts, so
the tab renders as a single block and the check cannot run.

This command tops the target organisation up with plainly-labelled scaffolding
cohorts (``QA Page Cohort 01`` ...), zero-padded so their ordering under
``ordering = ["name"]`` is the same in the database, in the page and to the eye
-- an unpadded ``10`` sorting before ``2`` would look exactly like the skipped
row the tester is hunting for.

Each cohort is a bare ``Cohort`` row: no members, no course registrations. The
inline renders only ``name``, and empty cohorts keep the fixture from touching
any progress percentage or report the tester may be mid-assertion on.

Idempotent: cohorts are matched on ``(site, organisation, name)`` -- the model's
own ``unique_cohort_name_per_organisation`` constraint -- so re-running tops up
to the requested number rather than duplicating.

Usage:
    uv run python manage.py qa_create_org_cohort_pagination
    uv run python manage.py qa_create_org_cohort_pagination \
        --site-name DemoDev --organisation-slug demodev --num-cohorts 30
"""

import djclick as click

from django.contrib.sites.models import Site

from freedom_ls.learner_management.admin import OrganisationCohortInline
from freedom_ls.learner_management.factories import CohortFactory
from freedom_ls.learner_management.models import Cohort
from freedom_ls.organisations.models import Organisation

DEFAULT_SITE_NAME = "DemoDev"
DEFAULT_ORGANISATION_SLUG = "demodev"
DEFAULT_NUM_COHORTS = 30
DEFAULT_NAME_PREFIX = "QA Page Cohort"


def _get_site(site_name: str) -> Site:
    try:
        return Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        available = list(Site.objects.values_list("name", flat=True))
        raise click.ClickException(
            f"Site '{site_name}' not found. Available: {available}"
        ) from e


def _get_organisation(slug: str, site: Site) -> Organisation:
    try:
        return Organisation._base_manager.get(slug=slug, site=site)
    except Organisation.DoesNotExist as e:
        available = list(
            Organisation._base_manager.filter(site=site).values_list("slug", flat=True)
        )
        raise click.ClickException(
            f"Organisation '{slug}' not found on site '{site.name}'. "
            f"Available: {available}"
        ) from e


def _cohort_name(prefix: str, index: int) -> str:
    """``QA Page Cohort 07`` -- zero-padded to at least two digits so the
    names sort the same way as the numbers they carry."""
    return f"{prefix} {index:02d}"


def _ensure_cohort(name: str, organisation: Organisation, site: Site) -> bool:
    """Create the named cohort if it is absent. True when one was created."""
    existing = Cohort._base_manager.filter(
        site=site, organisation=organisation, name=name
    ).first()
    if existing is not None:
        return False
    CohortFactory(name=name, organisation=organisation, site=site)
    return True


@click.command()
@click.option(
    "--site-name",
    default=DEFAULT_SITE_NAME,
    help=f"Site the cohorts belong to (default: '{DEFAULT_SITE_NAME}').",
)
@click.option(
    "--organisation-slug",
    default=DEFAULT_ORGANISATION_SLUG,
    help=f"Organisation to pad (default: '{DEFAULT_ORGANISATION_SLUG}').",
)
@click.option(
    "--num-cohorts",
    default=DEFAULT_NUM_COHORTS,
    type=int,
    help=f"How many scaffolding cohorts to ensure (default: {DEFAULT_NUM_COHORTS}).",
)
@click.option(
    "--name-prefix",
    default=DEFAULT_NAME_PREFIX,
    help=f"Prefix for the cohort names (default: '{DEFAULT_NAME_PREFIX}').",
)
def command(
    site_name: str, organisation_slug: str, num_cohorts: int, name_prefix: str
) -> None:
    """Top an organisation up with numbered cohorts so its admin tab paginates."""
    site = _get_site(site_name)
    organisation = _get_organisation(organisation_slug, site)

    before = Cohort._base_manager.filter(organisation=organisation).count()

    created: list[str] = []
    reused: list[str] = []
    for index in range(1, num_cohorts + 1):
        name = _cohort_name(name_prefix, index)
        if _ensure_cohort(name, organisation, site):
            created.append(name)
        else:
            reused.append(name)

    cohorts = Cohort._base_manager.filter(organisation=organisation).order_by("name")
    total = cohorts.count()
    off_site = cohorts.exclude(site=site).count()
    per_page = OrganisationCohortInline.per_page
    pages = -(-total // per_page)

    click.secho(
        "\n--- Organisation cohort pagination fixture ---", fg="cyan", bold=True
    )
    click.secho(f"Site:         {site.name} ({site.domain}) [id {site.pk}]", fg="cyan")
    click.secho(
        f"Organisation: {organisation.name} [slug: {organisation.slug}] "
        f"[pk: {organisation.pk}]",
        fg="cyan",
    )
    click.echo(
        f"Name pattern: '{_cohort_name(name_prefix, 1)}' ... "
        f"'{_cohort_name(name_prefix, num_cohorts)}'"
    )
    click.secho(f"Created: {len(created)}   Already present: {len(reused)}", fg="green")
    click.secho(
        f"Cohorts on this organisation: {before} -> {total}", fg="green", bold=True
    )
    click.secho(
        f"Rows carrying a site other than id {site.pk}: {off_site}"
        f"{'  <- correct' if off_site == 0 else '  <- WRONG'}",
        fg="green" if off_site == 0 else "red",
        bold=True,
    )
    click.secho(
        f"Inline per_page={per_page} (OrganisationCohortInline) -> {pages} page(s)",
        fg="green" if pages >= 3 else "yellow",
        bold=True,
    )
    click.secho(
        f"Admin: /admin/freedom_ls_organisations/organisation/{organisation.pk}/change/"
        "  (Cohorts tab)",
        fg="green",
    )
