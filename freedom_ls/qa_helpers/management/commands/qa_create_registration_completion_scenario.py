"""Seed the "registration completion + course access" QA scenario.

On a single site (default: DemoDev), idempotently ensures:

1. A FREE-access course (published, in the anonymous catalogue) whose access
   flow enrols a logged-in student immediately with no gate.
2. An APPLICATION-GATED course (published) reachable at ``/apply/<slug>/``.
   Both courses + the base learner are built by reusing the helpers from
   ``qa_create_course_access_types`` (factory-based, DRY).
3. A COMPLETE, login-ready student (verified allauth email, password == email)
   who is *registration-complete*: a ``QARegistrationCompletion`` row means
   ``RegistrationCompletionMiddleware`` lets them through. They are enrolled in
   NOTHING and have applied to NOTHING, so both course CTAs are exercisable.
4. A ``SiteSignupPolicy`` with ``allow_signups=True`` and one submittable
   ``additional_registration_forms`` entry (``QAProfileCompletionForm``), so a
   brand-new signup IS intercepted and routed to the completion page. Dev-
   default ``require_name`` / ``require_terms_acceptance`` are preserved (a
   policy row otherwise silently resets them to the model defaults).
"""

import djclick as click

from django.contrib.sites.models import Site

from freedom_ls.accounts.models import SiteSignupPolicy
from freedom_ls.accounts.registration_forms import get_incomplete_forms
from freedom_ls.course_applications.models import CourseApplication
from freedom_ls.qa_helpers.factories import QARegistrationCompletionFactory

# Reuse the factory-based builders from the sibling command (DRY).
from freedom_ls.qa_helpers.management.commands.qa_create_course_access_types import (
    FREE_COURSE_SLUG,
    FREE_COURSE_TITLE,
    GATED_COURSE_SLUG,
    GATED_COURSE_TITLE,
    _ensure_verified_email,
    _get_or_create_course,
    _get_or_create_learner,
)
from freedom_ls.student_management.models import UserCourseRegistration

COMPLETION_FORM_PATH = (
    "freedom_ls.qa_helpers.registration_forms.QAProfileCompletionForm"
)


@click.command()
@click.argument("site_name", default="DemoDev")
def command(site_name: str) -> None:
    """Seed the registration-completion + course-access QA scenario.

    SITE_NAME is the site to create data on (default: DemoDev).
    """
    try:
        site = Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        available = list(Site.objects.values_list("name", flat=True))
        raise click.ClickException(
            f"Site '{site_name}' not found. Available: {available}"
        ) from e

    # 1-3: base learner + free/gated courses (verified email, viewable topic).
    learner = _get_or_create_learner(site)
    _ensure_verified_email(learner)

    free_course = _get_or_create_course(
        site,
        title=FREE_COURSE_TITLE,
        slug=FREE_COURSE_SLUG,
        access_config={"access_type": "free"},
    )
    gated_course = _get_or_create_course(
        site,
        title=GATED_COURSE_TITLE,
        slug=GATED_COURSE_SLUG,
        access_config={"access_type": "application_gated"},
    )

    # Guarantee "enrolled in nothing / applied to nothing" so both CTAs work.
    UserCourseRegistration.objects.filter(user=learner, site=site).delete()
    CourseApplication.objects.filter(user=learner, site=site).delete()

    # 4: site signup policy — allow signups, require the completion form, and
    # preserve dev-default require_name / require_terms_acceptance (a fresh
    # policy row would otherwise reset them to the model defaults).
    policy, _ = SiteSignupPolicy.objects.update_or_create(
        site=site,
        defaults={
            "allow_signups": True,
            "require_name": True,
            "require_terms_acceptance": True,
            "additional_registration_forms": [COMPLETION_FORM_PATH],
        },
    )

    # Mark the seeded learner registration-complete (durable DB marker) so the
    # middleware does NOT intercept them even though the form is now required.
    QARegistrationCompletionFactory(user=learner)

    # Verify the gate behaves: seeded learner complete, hypothetical new signup gated.
    learner_incomplete = get_incomplete_forms(
        learner, policy.additional_registration_forms
    )

    reg_count = UserCourseRegistration.objects.filter(user=learner, site=site).count()
    app_count = CourseApplication.objects.filter(user=learner, site=site).count()

    click.secho(
        "\n--- Registration-Completion + Course-Access QA data ---",
        fg="cyan",
        bold=True,
    )
    click.secho(f"Site: {site.name} (domain: {site.domain})", fg="cyan")
    click.secho(
        f"FREE course:  '{free_course.title}'  slug={free_course.slug}  "
        f"access_config={free_course.access_config}  "
        f"viewable_items={len(free_course.viewable_items())}",
        fg="green",
    )
    click.secho(
        f"GATED course: '{gated_course.title}'  slug={gated_course.slug}  "
        f"access_config={gated_course.access_config}  "
        f"viewable_items={len(gated_course.viewable_items())}",
        fg="green",
    )
    click.secho(
        f"Student login: {learner.email} / {learner.email} "
        f"(verified, active={learner.is_active}, staff={learner.is_staff})",
        fg="green",
        bold=True,
    )
    click.secho(
        f"Student registrations: {reg_count} | applications: {app_count} "
        f"(both must be 0)",
        fg="green" if reg_count == 0 and app_count == 0 else "red",
        bold=True,
    )
    click.secho(
        f"SiteSignupPolicy: allow_signups={policy.allow_signups} "
        f"require_name={policy.require_name} "
        f"require_terms_acceptance={policy.require_terms_acceptance} "
        f"additional_registration_forms={policy.additional_registration_forms}",
        fg="green",
    )
    click.secho(
        f"Seeded student incomplete forms (must be []): "
        f"{[c.__name__ for c in learner_incomplete]}",
        fg="green" if not learner_incomplete else "red",
        bold=True,
    )
    click.secho(
        "New browser signups will be gated by RegistrationCompletionMiddleware "
        "until they submit 'How did you hear about us?'.",
        fg="yellow",
    )
