"""Create the three accounts for the application-review permission QA walkthrough.

Seeds (or resets to a known state) three DemoDev accounts:

- ``qa_applicant@email.com``  -- plain learner, no registrations, no applications
- ``qa_bystander@email.com``  -- identical shape to the applicant
- ``qa_reviewer@email.com``   -- ``is_staff`` with exactly three form_engine view
  permissions granted directly on the user, to prove that those three model
  permissions alone do NOT open the corresponding admin pages.

DemoDev-only convention: each account's password is set to its own email address
(the same convention ``create_demo_data`` uses), and each gets a verified+primary
allauth ``EmailAddress`` so login skips the email-confirmation step.

Re-running is idempotent AND destructive for the three accounts it owns: it
resets flags, password, permissions, group memberships, and strips every
CourseApplication / form sitting / course registration the applicant and
bystander hold. Do not point it at addresses a tester has customised.

Usage:
    uv run python manage.py qa_create_application_review_accounts
    uv run python manage.py qa_create_application_review_accounts --site-name DemoDev
"""

from typing import cast

import djclick as click
from allauth.account.models import EmailAddress

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.db import transaction

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.course_applications.models import CourseApplication
from freedom_ls.form_engine.models import (
    FormProgress,
    QuestionAnswer,
    QuestionAnswerFile,
)
from freedom_ls.learner_management.factories import LearnerFactory
from freedom_ls.learner_management.models import (
    CohortMembership,
    Learner,
    LearnerCourseRegistration,
)
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.organisations.utils import get_default_organisation

APPLICANT_EMAIL = "qa_applicant@email.com"
BYSTANDER_EMAIL = "qa_bystander@email.com"
REVIEWER_EMAIL = "qa_reviewer@email.com"

#: The only permissions the reviewer may hold. Resolved through ContentType so
#: the real app label is used whatever it happens to be (it is currently
#: ``freedom_ls_form_engine``, not ``form_engine``).
REVIEWER_PERMISSION_SPECS: list[
    tuple[type[QuestionAnswer | FormProgress | QuestionAnswerFile], str]
] = [
    (QuestionAnswer, "view_questionanswer"),
    (FormProgress, "view_formprogress"),
    (QuestionAnswerFile, "view_questionanswerfile"),
]


def _reviewer_permissions() -> list[Permission]:
    """Resolve the three reviewer permissions, failing loudly if one is missing."""
    permissions: list[Permission] = []
    for model, codename in REVIEWER_PERMISSION_SPECS:
        content_type = ContentType.objects.get_for_model(model)
        try:
            permissions.append(
                Permission.objects.get(content_type=content_type, codename=codename)
            )
        except Permission.DoesNotExist as e:
            raise click.ClickException(
                f"Permission '{content_type.app_label}.{codename}' does not exist. "
                "Run migrations first."
            ) from e
    return permissions


def _ensure_user(email: str, site: Site, *, is_staff: bool) -> tuple[User, bool]:
    """Create or reset a User on the given site. Returns (user, was_created).

    _base_manager: outside a request there is no ambient site, but an account
    with this email could exist on another Site and would then be invisible to
    a site-filtered lookup, producing a second row instead of a reset.
    """
    user = User._base_manager.filter(email=email).first()
    if user is None:
        created_user = cast(
            User,
            UserFactory(
                email=email,
                is_active=True,
                is_staff=is_staff,
                is_superuser=False,
                password=email,
                site=site,
            ),
        )
        return created_user, True

    user.site = site
    user.is_active = True
    user.is_staff = is_staff
    user.is_superuser = False
    user.set_password(email)
    user.save()
    return user, False


def _ensure_verified_email(user: User) -> None:
    """Ensure an allauth verified+primary EmailAddress exists for the user.

    update_or_create, not get_or_create: a user who has already tried to log in
    owns a row allauth wrote with verified=False, and get_or_create would find
    that row and leave it broken.
    """
    EmailAddress.objects.update_or_create(
        user=user,
        email=user.email,
        defaults={"verified": True, "primary": True},
    )


def _purge_course_data(user: User) -> dict[str, int]:
    """Strip every application, form sitting, registration and cohort membership
    the user holds.

    CourseProgress PROTECTs LearnerCourseRegistration, so the progress rows a
    registration minted must go before the registration itself. Cohort *course*
    registrations belong to the cohort rather than to this user, so the way to
    take a cohort-granted course away from one person is to delete their
    CohortMembership -- never the CohortCourseRegistration.
    """
    counts: dict[str, int] = {}

    applications = CourseApplication._base_manager.filter(user=user)
    counts["CourseApplication"] = applications.count()
    applications.delete()

    # After the applications: CourseApplication.form_progress is RESTRICT. The
    # cascade to QuestionAnswer and QuestionAnswerFile is what sweeps the stored
    # files, through the post_delete receiver.
    sittings = FormProgress._base_manager.filter(user=user)
    counts["FormProgress"] = sittings.count()
    sittings.delete()

    learners = Learner._base_manager.filter(user=user)

    progress = CourseProgress._base_manager.filter(learner__in=learners)
    counts["CourseProgress"] = progress.count()
    progress.delete()

    registrations = LearnerCourseRegistration._base_manager.filter(learner__in=learners)
    counts["LearnerCourseRegistration"] = registrations.count()
    registrations.delete()

    memberships = CohortMembership._base_manager.filter(learner__in=learners)
    counts["CohortMembership"] = memberships.count()
    memberships.delete()

    return counts


def _describe(user: User) -> str:
    """One-line summary of the state a QA tester needs to see."""
    perms = sorted(
        f"{p.content_type.app_label}.{p.codename}"
        for p in user.user_permissions.select_related("content_type")
    )
    applications = CourseApplication._base_manager.filter(user=user).count()
    sittings = FormProgress._base_manager.filter(user=user).count()
    registrations = LearnerCourseRegistration._base_manager.filter(
        learner__user=user
    ).count()
    memberships = CohortMembership._base_manager.filter(learner__user=user).count()
    return (
        f"pk={user.pk} site={user.site.name} is_staff={user.is_staff} "
        f"is_superuser={user.is_superuser} is_active={user.is_active}\n"
        f"      permissions={perms or 'none'} groups="
        f"{sorted(user.groups.values_list('name', flat=True)) or 'none'}\n"
        f"      applications={applications} form_sittings={sittings} "
        f"learner_registrations={registrations} cohort_memberships={memberships}"
    )


@click.command()
@click.option("--site-name", default="DemoDev", help="Site name (default: 'DemoDev')")
def command(site_name: str) -> None:
    try:
        site = Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        raise click.ClickException(f"Site with name '{site_name}' not found.") from e

    organisation = get_default_organisation(site)
    permissions = _reviewer_permissions()

    click.secho(f"Site: {site.name} (id={site.pk}, {site.domain})", fg="cyan")
    click.secho(f"Default organisation: {organisation.name}", fg="cyan")
    click.echo("")

    with transaction.atomic():
        # -- the two plain learners -------------------------------------
        for email, label in (
            (APPLICANT_EMAIL, "applicant"),
            (BYSTANDER_EMAIL, "bystander"),
        ):
            user, created = _ensure_user(email, site, is_staff=False)
            _ensure_verified_email(user)
            LearnerFactory(user=user, organisation=organisation, site=site)
            user.user_permissions.clear()
            user.groups.clear()
            purged = _purge_course_data(user)
            verb = "Created" if created else "Reset"
            click.secho(
                f"  {verb} {label}: {email}", fg="green" if created else "yellow"
            )
            removed = {k: v for k, v in purged.items() if v}
            if removed:
                click.secho(f"      removed: {removed}", fg="red")

        # -- the staff reviewer -----------------------------------------
        reviewer, created = _ensure_user(REVIEWER_EMAIL, site, is_staff=True)
        _ensure_verified_email(reviewer)
        reviewer.groups.clear()
        reviewer.user_permissions.set(permissions)
        verb = "Created" if created else "Reset"
        click.secho(
            f"  {verb} reviewer: {REVIEWER_EMAIL}", fg="green" if created else "yellow"
        )

    click.echo("")
    click.secho("== Final state ==", fg="cyan", bold=True)
    for email in (APPLICANT_EMAIL, BYSTANDER_EMAIL, REVIEWER_EMAIL):
        user = User._base_manager.get(email=email)
        click.secho(f"  {email}", fg="green", bold=True)
        click.echo(f"      {_describe(user)}")

    click.echo("")
    click.secho("== Login ==", fg="cyan", bold=True)
    click.echo(f"  Site      : http://{site.domain}/")
    click.echo("  Password  : same as the email address (DemoDev convention)")
    click.echo(f"  Admin     : http://{site.domain}/admin/  (reviewer only)")
