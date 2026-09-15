"""Create (or reset) a single clean applicant persona for form/application QA.

The shape this builds is the one an application-forms QA plan keeps asking for:

* a plain learner -- ``is_staff=False``, ``is_superuser=False``, ``is_active=True``;
* a verified + primary allauth ``EmailAddress`` so login skips the
  "Verify Your Email Address" interstitial;
* password equal to the email address (the DemoDev convention);
* **no** ``CourseApplication`` and **no** ``FormProgress``, so every form start
  screen reads "Start Form" and the by-application courses still offer "Apply now";
* optionally registered for named free courses, via the same two rows
  ``initiate_course_access`` writes (``Learner`` + ``LearnerCourseRegistration``).

Deletion order is forced by the database: ``CourseApplication.form_progress`` is
RESTRICT, so applications go before the sittings they name; ``CourseProgress``
PROTECTs ``LearnerCourseRegistration``, so progress goes before registrations.

Re-running is idempotent AND destructive for the named account: it resets the
password and flags and strips every application, sitting, registration and
cohort membership the account holds. Point it only at QA addresses.

Usage:
    uv run python manage.py qa_create_clean_applicant \
        --email qa.applicant.a@email.com \
        --register-course-slug functionality-demo-show-end-with-topic

    uv run python manage.py qa_create_clean_applicant \
        --email qa.applicant.b@email.com --site-name DemoDev
"""

from typing import cast

import djclick as click
from allauth.account.models import EmailAddress

from django.contrib.sites.models import Site
from django.db import transaction

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import Course
from freedom_ls.course_applications.models import CourseApplication
from freedom_ls.form_engine.models import FormProgress
from freedom_ls.learner_management.factories import (
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import (
    CohortMembership,
    Learner,
    LearnerCourseRegistration,
)
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.organisations.models import Organisation
from freedom_ls.organisations.utils import get_default_organisation


def _get_site(site_name: str) -> Site:
    try:
        return Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        available = list(Site.objects.values_list("name", flat=True))
        raise click.ClickException(
            f"Site '{site_name}' not found. Available: {available}"
        ) from e


def _get_courses(site: Site, course_slugs: tuple[str, ...]) -> list[Course]:
    """Resolve every requested slug on the site, failing loudly on a typo."""
    courses: list[Course] = []
    for slug in course_slugs:
        course = Course._base_manager.filter(site=site, slug=slug).first()
        if course is None:
            raise click.ClickException(
                f"No course with slug '{slug}' on site '{site.name}'."
            )
        courses.append(course)
    return courses


def _ensure_user(email: str, site: Site) -> tuple[User, bool]:
    """Create or reset a plain learner User on the given site.

    _base_manager: outside a request there is no ambient site, and an account
    with this email could live on another Site where a site-filtered lookup
    would miss it and mint a duplicate instead of resetting.
    """
    user = User._base_manager.filter(email=email).first()
    if user is None:
        created = cast(
            User,
            UserFactory(
                email=email,
                is_active=True,
                is_staff=False,
                is_superuser=False,
                password=email,
                site=site,
            ),
        )
        return created, True

    user.site = site
    user.is_active = True
    user.is_staff = False
    user.is_superuser = False
    user.set_password(email)
    user.save()
    return user, False


def _ensure_verified_email(user: User) -> None:
    """Ensure a verified + primary allauth EmailAddress exists for the user.

    update_or_create, not get_or_create: an account that has already attempted
    a login owns a row allauth wrote with verified=False, and get_or_create
    would find that row and leave it broken.
    """
    EmailAddress.objects.update_or_create(
        user=user,
        email=user.email,
        defaults={"verified": True, "primary": True},
    )


def _purge_course_data(user: User) -> list[str]:
    """Strip applications, sittings, registrations and memberships, in FK order.

    Returns one human-readable line per deleted row group, naming the pks, so a
    mis-targeted run is visible in the output rather than silent.
    """
    lines: list[str] = []

    applications = CourseApplication._base_manager.filter(user=user)
    for application in applications.select_related("course"):
        lines.append(
            f"CourseApplication {application.pk} "
            f"(course={application.course.slug}, form_progress={application.form_progress_id})"
        )
    if applications.exists():
        lines.append(f"  -> deleted: {applications.delete()}")

    sittings = FormProgress._base_manager.filter(user=user)
    for sitting in sittings.select_related("form"):
        lines.append(f"FormProgress {sitting.pk} (form={sitting.form.title!r})")
    if sittings.exists():
        lines.append(f"  -> deleted: {sittings.delete()}")

    learners = Learner._base_manager.filter(user=user)

    progress = CourseProgress._base_manager.filter(learner__in=learners)
    for row in progress.select_related("course"):
        lines.append(f"CourseProgress {row.pk} (course={row.course.slug})")
    if progress.exists():
        lines.append(f"  -> deleted: {progress.delete()}")

    registrations = LearnerCourseRegistration._base_manager.filter(learner__in=learners)
    for registration in registrations.select_related("course"):
        lines.append(
            f"LearnerCourseRegistration {registration.pk} (course={registration.course.slug})"
        )
    if registrations.exists():
        lines.append(f"  -> deleted: {registrations.delete()}")

    memberships = CohortMembership._base_manager.filter(learner__in=learners)
    for membership in memberships.select_related("cohort"):
        lines.append(
            f"CohortMembership {membership.pk} (cohort={membership.cohort.name})"
        )
    if memberships.exists():
        lines.append(f"  -> deleted: {memberships.delete()}")

    return lines


def _register(
    user: User, organisation: Organisation, site: Site, course: Course
) -> None:
    """Reproduce the self-service enrolment shape of ``initiate_course_access``.

    LearnerFactory delegates to ensure_learner, so it returns the persona's
    existing Learner rather than a second row. The registration's post_save
    receiver mints the CourseProgress at 0%.
    """
    learner = LearnerFactory(user=user, organisation=organisation, site=site)
    LearnerCourseRegistrationFactory(
        learner=learner, course=course, site=site, is_active=True
    )


def _describe(user: User) -> str:
    """One-line summary of the state a QA tester needs to see."""
    applications = CourseApplication._base_manager.filter(user=user).count()
    sittings = FormProgress._base_manager.filter(user=user).count()
    registrations = LearnerCourseRegistration._base_manager.filter(
        learner__user=user, is_active=True
    )
    email_address = EmailAddress.objects.filter(user=user, email=user.email).first()
    slugs = sorted(
        registration.course.slug
        for registration in registrations.select_related("course")
    )
    return (
        f"pk={user.pk} site={user.site.name} is_staff={user.is_staff} "
        f"is_superuser={user.is_superuser} is_active={user.is_active} "
        f"email_verified={email_address.verified if email_address else None}\n"
        f"      applications={applications} form_sittings={sittings}\n"
        f"      registered_for={slugs or 'nothing'}"
    )


@click.command()
@click.option("--email", required=True, help="Email address of the QA applicant.")
@click.option(
    "--register-course-slug",
    "register_course_slugs",
    multiple=True,
    help="Register the applicant for this course (repeatable). Default: none.",
)
@click.option(
    "--site-name",
    default="DemoDev",
    help="Site name the account and courses live on (default: 'DemoDev').",
)
def command(email: str, register_course_slugs: tuple[str, ...], site_name: str) -> None:
    """Create or reset one clean, verified, application-free QA applicant."""
    site = _get_site(site_name)
    organisation = get_default_organisation(site)
    courses = _get_courses(site, register_course_slugs)

    click.secho("\n--- Clean applicant ---", fg="cyan", bold=True)
    click.secho(f"Site:         {site.name} ({site.domain}) [id {site.pk}]", fg="cyan")
    click.secho(f"Organisation: {organisation.name}", fg="cyan")

    with transaction.atomic():
        user, created = _ensure_user(email, site)
        _ensure_verified_email(user)
        LearnerFactory(user=user, organisation=organisation, site=site)
        removed = _purge_course_data(user)
        for course in courses:
            _register(user, organisation, site, course)

    verb = "Created" if created else "Reset"
    click.secho(f"\n{verb}: {email}", fg="green" if created else "yellow", bold=True)
    if removed:
        click.secho("Removed:", fg="red", bold=True)
        for line in removed:
            click.secho(f"  {line}", fg="red")
    else:
        click.secho("Removed: nothing (account held no QA residue).", fg="green")

    user.refresh_from_db()
    click.secho("\n== Final state ==", fg="cyan", bold=True)
    click.echo(f"  {_describe(user)}")

    click.secho("\n== Login ==", fg="cyan", bold=True)
    click.echo(f"  Email    : {email}")
    click.echo(f"  Password : {email}   (same as the email; DemoDev convention)")
