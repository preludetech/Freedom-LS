"""Seed a small ``form_engine`` tree on a second site, for admin site-scoping QA.

The dev database only ever carries ``form_engine`` rows for one site, so a
Django-admin changelist filtered by ``SiteAwareModelAdmin`` looks identical to
an unfiltered one. This command adds a deliberately tiny, clearly labelled
Form / FormPage / FormQuestion / QuestionOption tree on a *different* site so
the per-site filtering is observable in the browser.

Nothing that already exists is touched: the whole tree is looked up by the
form's slug on the target site and created only when missing.
"""

from typing import cast

import djclick as click

from django.contrib.sites.models import Site
from django.db.models import Count

from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
    QuestionOptionFactory,
)
from freedom_ls.form_engine.models import (
    Form,
    FormPage,
    FormQuestion,
    FormStrategy,
    QuestionOption,
    QuestionType,
)

FORM_TITLE = "QA Bloom Site Scoping Form"
FORM_SLUG = "qa-bloom-site-scoping-form"

PAGE_TITLE = "QA Site Scoping Page"
PAGE_SLUG = "qa-site-scoping-page"

QUESTION = "Which site does this row belong to?"
OPTIONS = (("Bloom", True), ("DemoDev", False))


def _get_site(site_name: str) -> Site:
    try:
        return Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        available = list(Site.objects.values_list("name", flat=True))
        raise click.ClickException(
            f"Site '{site_name}' not found. Available: {available}"
        ) from e


def _build_form(site: Site) -> tuple[Form, bool]:
    """Create the form tree on ``site``. Returns ``(form, created)``.

    Idempotent on ``(site, slug)`` — ``Form.Meta.unique_together`` — so a
    re-run is a no-op rather than a duplicate or an IntegrityError. Every
    factory call passes ``site=site`` explicitly and passes its real parent, so
    no ``SubFactory`` fires and no row can land on a different site: without
    an HTTP request there is no thread-local site for ``SiteAwareFactory`` to
    fall back on.

    ``_base_manager`` is used for the lookup because ``SiteAwareManager``
    silently narrows to the thread-local request's site, which a management
    command does not have.
    """
    existing: Form | None = Form._base_manager.filter(site=site, slug=FORM_SLUG).first()
    if existing is not None:
        return existing, False

    form = cast(
        Form,
        FormFactory(
            site=site,
            title=FORM_TITLE,
            slug=FORM_SLUG,
            strategy=FormStrategy.QUIZ,
            quiz_show_incorrect=True,
            quiz_pass_percentage=50,
        ),
    )
    page = cast(
        FormPage,
        FormPageFactory(
            site=site,
            form=form,
            title=PAGE_TITLE,
            slug=PAGE_SLUG,
            order=0,
        ),
    )
    question = cast(
        FormQuestion,
        FormQuestionFactory(
            site=site,
            form_page=page,
            question=QUESTION,
            type=QuestionType.MULTIPLE_CHOICE,
            required=True,
            order=0,
        ),
    )
    for index, (text, correct) in enumerate(OPTIONS):
        QuestionOptionFactory(
            site=site,
            question=question,
            text=text,
            value=str(index + 1),
            order=index,
            correct=correct,
        )
    return form, True


@click.command()
@click.argument("site_name", default="Bloom")
def command(site_name: str) -> None:
    """Seed a form_engine tree on a second site for admin site-scoping QA.

    SITE_NAME is the site to create the data on (default: Bloom).
    """
    site = _get_site(site_name)
    form, created = _build_form(site)

    click.secho("\n--- Summary ---", fg="cyan", bold=True)
    click.secho(
        f"{'Created' if created else 'Already present (no changes made)'}: "
        f"{form.title}  [slug: {form.slug}]  on site {site.name} ({site.domain})",
        fg="green" if created else "yellow",
        bold=True,
    )

    click.secho("\nform_engine rows per site:", fg="cyan", bold=True)
    for model in (Form, FormPage, FormQuestion, QuestionOption):
        counts = ", ".join(
            f"{name}={count}"
            for name, count in sorted(
                model._base_manager.values_list("site__name")
                .order_by("site__name")
                .annotate(total=Count("id"))
            )
        )
        click.secho(f"  {model.__name__:<15} {counts}", fg="cyan")
