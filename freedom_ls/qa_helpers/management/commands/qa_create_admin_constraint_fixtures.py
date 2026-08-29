"""Seed the admin rows whose *uniqueness constraints* need exercising in the browser.

Every fixture here exists so a QA tester can try to create a DUPLICATE of it
through the Django admin and watch the constraint (or its
ConstraintValidationFormMixin form error) fire:

1. Two ``WebhookEndpoint`` rows pointing at the reserved ``.invalid`` TLD, so
   nothing is ever actually delivered. One of them carries a Jinja2
   transformation that references a ``WebhookSecret`` by name, which is the
   only way an endpoint and a secret are associated -- there is no FK.
2. Two ``WebhookSecret`` rows: one referenced by the templated endpoint, one
   parked purely so its NAME already exists
   (``unique_webhook_secret_name_per_site``).
3. One ``CourseInterest`` row (``unique_course_interest``).
4. A second ``Learner`` row for an existing user on a NON-default
   Organisation (``unique_learner_per_organisation``), plus one Cohort in each
   of two non-default Organisations so that the per-organisation scope of
   ``unique_cohort_name_per_organisation`` can be shown to permit the same
   name twice.

No ``WebhookDelivery`` rows are created: those are meant to come from the
admin's "Send Test" action.

Idempotent -- every row is matched on its own natural key, so a re-run reports
``kept`` and writes nothing.

Usage:
    uv run python manage.py qa_create_admin_constraint_fixtures
    uv run python manage.py qa_create_admin_constraint_fixtures DemoDev
"""

from typing import cast

import djclick as click

from django.contrib.sites.models import Site

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import Course
from freedom_ls.course_interest.factories import CourseInterestFactory
from freedom_ls.course_interest.models import CourseInterest
from freedom_ls.learner_management.factories import CohortFactory, LearnerFactory
from freedom_ls.learner_management.models import Cohort, Learner
from freedom_ls.organisations.models import Organisation
from freedom_ls.webhooks.factories import WebhookEndpointFactory, WebhookSecretFactory
from freedom_ls.webhooks.models import WebhookEndpoint, WebhookSecret

# WebhookSecret.name is validated by SECRET_NAME_VALIDATOR
# (^[a-zA-Z_][a-zA-Z0-9_]*$) -- underscores, never hyphens, or the admin form
# rejects the name before the uniqueness check is ever reached.
# S105 is suppressed below: these are secret *names* (the identifier a
# template looks up), not secret values.
DUPLICATE_TARGET_SECRET_NAME = "qa_existing_secret"  # noqa: S105  # pragma: allowlist secret
TEMPLATE_SECRET_NAME = "qa_hook_api_key"  # noqa: S105  # pragma: allowlist secret

# example.invalid is reserved by RFC 2606 and never resolves, so the admin's
# "Send Test" action produces a delivery row that fails at DNS rather than
# reaching a real host.
ENDPOINT_ONE_URL = "https://example.invalid/hooks/one"
ENDPOINT_TWO_URL = "https://example.invalid/hooks/two"

# The only association between an endpoint and a WebhookSecret: the secret is
# looked up by name at render time, so TEMPLATE_SECRET_NAME must appear
# literally here. WebhookEndpoint.clean() refuses to save the endpoint if the
# named secret does not exist on the site.
ENDPOINT_ONE_BODY_TEMPLATE = (
    '{"event": "{{ event.type }}", "event_id": "{{ event.id }}"}'
)
ENDPOINT_ONE_HEADERS_TEMPLATE = '{"X-Api-Key": "{{ secrets.qa_hook_api_key }}"}'

INTEREST_USER_EMAIL = "demodev_s2@email.com"
INTEREST_COURSE_SLUG = "standard-markdown-demo-finance"

SECOND_ORGANISATION_SLUG = "rpas-training"
THIRD_ORGANISATION_SLUG = "northside"
SECOND_ORGANISATION_COHORT_NAME = "QA Org Scope Cohort"
THIRD_ORGANISATION_COHORT_NAME = "QA Northside Cohort"


def _ensure_secret(site: Site, name: str, value: str, description: str) -> str:
    """Get-or-create a WebhookSecret by (site, name); return a status word."""
    existing = WebhookSecret._base_manager.filter(site=site, name=name).first()
    if existing is not None:
        click.secho(f"  kept    WebhookSecret {name!r} pk={existing.pk}", fg="yellow")
        return "kept"
    secret = cast(
        WebhookSecret,
        WebhookSecretFactory(
            site=site, name=name, encrypted_value=value, description=description
        ),
    )
    click.secho(f"  created WebhookSecret {name!r} pk={secret.pk}", fg="green")
    return "created"


def _ensure_endpoint(site: Site, url: str, **fields: object) -> WebhookEndpoint:
    """Get-or-create a WebhookEndpoint by (site, url), validating before insert."""
    existing = WebhookEndpoint._base_manager.filter(site=site, url=url).first()
    if existing is not None:
        click.secho(
            f"  kept    WebhookEndpoint {existing.description!r} pk={existing.pk}",
            fg="yellow",
        )
        return existing
    endpoint = cast(
        WebhookEndpoint, WebhookEndpointFactory.build(site=site, url=url, **fields)
    )
    # full_clean here rather than after saving: it runs the same event-type,
    # template and referenced-secret checks the admin form runs, so a fixture
    # that the admin would refuse to re-save never reaches the database.
    endpoint.full_clean()
    endpoint.save()
    click.secho(
        f"  created WebhookEndpoint {endpoint.description!r} pk={endpoint.pk}",
        fg="green",
    )
    return endpoint


def _ensure_cohort(site: Site, organisation: Organisation, name: str) -> Cohort:
    """Get-or-create a Cohort by (site, organisation, name)."""
    existing = Cohort._base_manager.filter(
        site=site, organisation=organisation, name=name
    ).first()
    if existing is not None:
        click.secho(
            f"  kept    Cohort {name!r} in {organisation.name!r} pk={existing.pk}",
            fg="yellow",
        )
        return existing
    cohort = cast(
        Cohort, CohortFactory(site=site, organisation=organisation, name=name)
    )
    click.secho(
        f"  created Cohort {name!r} in {organisation.name!r} pk={cohort.pk}", fg="green"
    )
    return cohort


def _get_organisation(site: Site, slug: str) -> Organisation:
    try:
        return Organisation._base_manager.get(site=site, slug=slug)
    except Organisation.DoesNotExist as exc:
        raise click.ClickException(
            f"No Organisation with slug {slug!r} on site {site.name!r}. "
            "Run qa_create_organisations first."
        ) from exc


@click.command()
@click.argument("site_name", default="DemoDev")
def command(site_name: str) -> None:
    try:
        site = Site.objects.get(name=site_name)
    except Site.DoesNotExist as exc:
        raise click.ClickException(f"Site with name {site_name!r} not found.") from exc

    click.secho(f"Site: {site.name} (pk={site.pk})", fg="cyan", bold=True)

    click.secho("\nWebhook secrets", fg="cyan", bold=True)
    _ensure_secret(
        site,
        TEMPLATE_SECRET_NAME,
        "qa-not-a-real-api-key-0123456789",
        "Referenced by the templated QA endpoint's headers_template.",
    )
    _ensure_secret(
        site,
        DUPLICATE_TARGET_SECRET_NAME,
        "qa-duplicate-me-value",
        "Exists so its NAME can be duplicated through the admin add form.",
    )

    click.secho("\nWebhook endpoints", fg="cyan", bold=True)
    _ensure_endpoint(
        site,
        ENDPOINT_ONE_URL,
        description="QA Endpoint One (templated, uses qa_hook_api_key)",
        event_types=["user.registered", "course.registered"],
        http_method="POST",
        content_type="application/json",
        auth_type="none",
        body_template=ENDPOINT_ONE_BODY_TEMPLATE,
        headers_template=ENDPOINT_ONE_HEADERS_TEMPLATE,
    )
    _ensure_endpoint(
        site,
        ENDPOINT_TWO_URL,
        description="QA Endpoint Two (plain, signing auth)",
        event_types=["course.completed"],
    )

    click.secho("\nCourse interest", fg="cyan", bold=True)
    user = User._base_manager.filter(email=INTEREST_USER_EMAIL).first()
    if user is None:
        raise click.ClickException(f"No user {INTEREST_USER_EMAIL!r}.")
    course = Course._base_manager.filter(site=site, slug=INTEREST_COURSE_SLUG).first()
    if course is None:
        raise click.ClickException(
            f"No course {INTEREST_COURSE_SLUG!r} on {site.name!r}. "
            "Run content_save ./demo_content first."
        )
    interest = CourseInterest._base_manager.filter(
        site=site, user=user, course=course
    ).first()
    if interest is None:
        interest = cast(
            CourseInterest, CourseInterestFactory(site=site, user=user, course=course)
        )
        click.secho(
            f"  created CourseInterest pk={interest.pk} "
            f"{user.email} -> {course.title!r}",
            fg="green",
        )
    else:
        click.secho(f"  kept    CourseInterest pk={interest.pk}", fg="yellow")

    click.secho("\nOrganisations, learners and cohorts", fg="cyan", bold=True)
    second_org = _get_organisation(site, SECOND_ORGANISATION_SLUG)
    third_org = _get_organisation(site, THIRD_ORGANISATION_SLUG)

    already = Learner._base_manager.filter(user=user, organisation=second_org).exists()
    learner = cast(
        Learner, LearnerFactory(site=site, user=user, organisation=second_org)
    )
    click.secho(
        f"  {'kept   ' if already else 'created'} Learner pk={learner.pk} "
        f"{user.email} -> {second_org.name!r}",
        fg="yellow" if already else "green",
    )

    _ensure_cohort(site, second_org, SECOND_ORGANISATION_COHORT_NAME)
    _ensure_cohort(site, third_org, THIRD_ORGANISATION_COHORT_NAME)

    click.secho("\nDone.", fg="cyan", bold=True)
