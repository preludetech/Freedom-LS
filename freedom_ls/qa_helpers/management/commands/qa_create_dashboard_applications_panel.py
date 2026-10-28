"""Seed the dashboard's "Your applications" panel for a visual check.

Idempotently writes, on one site (default: DemoDev):

* ``demodev@email.com`` (must already exist -- ``create_demo_data``; its password
  is left alone) holds exactly seven applications on seven QA gated courses,
  four submitted and three drafts, created a day apart so the panel's
  newest-first order is unambiguous. The three newest -- the panel's first page
  -- are draft, submitted, draft. Any other application this user holds on the
  site is withdrawn.
* ``qa-one-app@example.com`` holds exactly one draft application.
* ``qa-no-apps@example.com`` holds no applications.

Each of the three is registered for one free demo course, so a course section
renders below the panel. The two QA personas are created login-ready: password
== email, verified primary EmailAddress, not staff.

Withdrawing an application deletes the application first and its sitting
second: ``CourseApplication.form_progress`` is RESTRICT, so the reverse order
raises. Every deletion is printed with the counts ``.delete()`` returned.

The login convention in this project is password == email address.
"""

from dataclasses import dataclass
from datetime import timedelta
from typing import cast

import djclick as click
from allauth.account.models import EmailAddress

from django.contrib.sites.models import Site
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import Course, CourseVisibility
from freedom_ls.course_applications.factories import CourseApplicationFactory
from freedom_ls.course_applications.models import CourseApplication
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormProgressFactory,
    FormQuestionFactory,
    QuestionAnswerFactory,
)
from freedom_ls.form_engine.models import (
    Form,
    FormProgress,
    FormQuestion,
    FormStrategy,
    QuestionAnswer,
)
from freedom_ls.learner_management.factories import LearnerCourseRegistrationFactory
from freedom_ls.learner_management.models import LearnerCourseRegistration
from freedom_ls.learner_management.utils import ensure_learner
from freedom_ls.learner_progress.utils import ensure_course_progress_record
from freedom_ls.organisations.utils import get_default_organisation

DEMODEV_EMAIL = "demodev@email.com"
ONE_APP_EMAIL = "qa-one-app@example.com"
NO_APPS_EMAIL = "qa-no-apps@example.com"

FREE_COURSE_SLUG = "functionality-demo-show-end-with-topic"

FORM_SLUG = "qa-dashboard-applications-form"
FORM_TITLE = "QA dashboard applications form"
QUESTION_TEXT = "Why do you want to join this course?"


@dataclass(frozen=True)
class SeededApplication:
    title: str
    days_ago: int
    submitted: bool


#: demodev's seven, newest first. Page one (3 per page) is draft, submitted, draft.
DEMODEV_APPLICATIONS = [
    SeededApplication("Cybersecurity Incident Response", 1, False),
    SeededApplication("Applied Machine Learning Bootcamp", 2, True),
    SeededApplication("Sustainable Urban Design Studio", 3, False),
    SeededApplication("Clinical Research Fundamentals", 4, True),
    SeededApplication("Leadership in Remote Teams", 5, True),
    SeededApplication("Professional Grant Writing", 6, False),
    SeededApplication("Advanced Data Visualisation", 7, True),
]

ONE_APP_APPLICATIONS = [
    SeededApplication("Community Health Worker Certificate", 2, False),
]


def _get_site(site_name: str) -> Site:
    try:
        return Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        available = list(Site.objects.values_list("name", flat=True))
        raise click.ClickException(
            f"Site '{site_name}' not found. Available: {available}"
        ) from e


def _get_existing_user(email: str) -> User:
    user: User | None = User.objects.filter(email=email).first()
    if user is None:
        raise click.ClickException(
            f"User '{email}' not found. Run `manage.py create_demo_data` first."
        )
    return user


def _get_or_create_persona(site: Site, email: str, first: str, last: str) -> User:
    """A login-ready learner whose password is their email."""
    user: User | None = User.objects.filter(email=email).first()
    if user is None:
        user = cast(
            User,
            UserFactory(
                email=email, first_name=first, last_name=last, password=email, site=site
            ),
        )
    else:
        user.is_active = True
        user.first_name = first
        user.last_name = last
        user.set_password(email)
        user.save(update_fields=["is_active", "first_name", "last_name", "password"])
    # update_or_create flips an unverified row allauth may already have written.
    EmailAddress.objects.update_or_create(
        user=user, email=user.email, defaults={"verified": True, "primary": True}
    )
    return user


def _ensure_form(site: Site) -> tuple[Form, FormQuestion]:
    """One shared unscored application form with a single long-text question."""
    form: Form | None = Form._base_manager.filter(slug=FORM_SLUG, site=site).first()
    if form is None:
        form = cast(
            Form,
            FormFactory(
                title=FORM_TITLE,
                slug=FORM_SLUG,
                strategy=FormStrategy.UNSCORED,
                site=site,
            ),
        )
        page = FormPageFactory(form=form, order=0, title="About you", site=site)
        FormQuestionFactory(
            form_page=page,
            type="long_text",
            order=0,
            question=QUESTION_TEXT,
            required=False,
            site=site,
        )
    question: FormQuestion = FormQuestion._base_manager.get(
        form_page__form=form, question=QUESTION_TEXT
    )
    return form, question


def _ensure_gated_course(site: Site, title: str, form: Form) -> Course:
    from django.utils.text import slugify

    slug = f"qa-{slugify(title)}"
    fields = {
        "title": title,
        "description": f"{title}: an application-gated QA course.",
        "access_config": {"access_type": "application_gated"},
        "visibility": CourseVisibility.PUBLISHED,
        "application_form": form,
    }
    course: Course | None = Course._base_manager.filter(slug=slug, site=site).first()
    if course is None:
        return cast(Course, CourseFactory(slug=slug, site=site, **fields))
    for name, value in fields.items():
        setattr(course, name, value)
    course.save(update_fields=list(fields.keys()))
    return course


def _withdraw(application: CourseApplication) -> None:
    """Delete the application, then the sitting it named (RESTRICT order)."""
    sitting_pk = application.form_progress_id
    click.echo(
        f"  withdrawing {application} course={application.course.slug} "
        f"user={application.user.email if application.user else None}"
    )
    click.echo(f"    CourseApplication.delete() -> {application.delete()}")
    if sitting_pk is not None:
        result = FormProgress._base_manager.filter(pk=sitting_pk).delete()
        click.echo(f"    FormProgress.delete() -> {result}")


def _ensure_application(
    site: Site,
    user: User,
    seeded: SeededApplication,
    form: Form,
    question: FormQuestion,
) -> CourseApplication:
    course = _ensure_gated_course(site, seeded.title, form)
    application: CourseApplication | None = (
        CourseApplication._base_manager.filter(site=site, user=user, course=course)
        .select_related("form_progress")
        .first()
    )
    if application is None or application.form_progress is None:
        if application is not None:
            _withdraw(application)
        new_sitting = FormProgressFactory(user=user, form=form, site=site)
        application = cast(
            CourseApplication,
            CourseApplicationFactory(
                user=user, course=course, form_progress=new_sitting, site=site
            ),
        )
    sitting = cast(FormProgress, application.form_progress)

    created_at = timezone.now() - timedelta(days=seeded.days_ago)
    QuestionAnswer._base_manager.filter(form_progress=sitting).delete()
    if seeded.submitted:
        QuestionAnswerFactory(
            form_progress=sitting,
            question=question,
            text_answer=f"I want to build real skills in {seeded.title.lower()}.",
            site=site,
        )
    FormProgress._base_manager.filter(pk=sitting.pk).update(
        start_time=created_at,
        completed_time=created_at + timedelta(minutes=20) if seeded.submitted else None,
    )
    CourseApplication._base_manager.filter(pk=application.pk).update(
        created_at=created_at
    )
    return application


def _seed_applications(
    site: Site,
    user: User,
    wanted: list[SeededApplication],
    form: Form,
    question: FormQuestion,
) -> None:
    keep = {
        _ensure_application(site, user, seeded, form, question).pk for seeded in wanted
    }
    stale = (
        CourseApplication._base_manager.filter(site=site, user=user)
        .exclude(pk__in=keep)
        .select_related("course", "user")
    )
    for application in stale:
        _withdraw(application)


def _register_free_course(site: Site, user: User, course: Course) -> None:
    learner = ensure_learner(user, get_default_organisation(site))
    registration: LearnerCourseRegistration | None = (
        LearnerCourseRegistration._base_manager.filter(
            learner=learner, course=course, site=site
        ).first()
    )
    if registration is None:
        registration = cast(
            LearnerCourseRegistration,
            LearnerCourseRegistrationFactory(learner=learner, course=course, site=site),
        )
    elif not registration.is_active:
        registration.is_active = True
        registration.save(update_fields=["is_active"])
    ensure_course_progress_record(learner, course, registration)


@click.command()
@click.option("--site-name", default="DemoDev", show_default=True)
def command(site_name: str) -> None:
    """Seed demodev (7 applications), qa-one-app (1 draft) and qa-no-apps (none)."""
    site = _get_site(site_name)
    free_course: Course | None = Course._base_manager.filter(
        slug=FREE_COURSE_SLUG, site=site
    ).first()
    if free_course is None:
        raise click.ClickException(
            f"Free course '{FREE_COURSE_SLUG}' not found on '{site.name}'. Run "
            f"`manage.py content_save ./demo_content {site.name}` first."
        )
    form, question = _ensure_form(site)

    personas: list[tuple[User, list[SeededApplication]]] = [
        (_get_existing_user(DEMODEV_EMAIL), DEMODEV_APPLICATIONS),
        (
            _get_or_create_persona(site, ONE_APP_EMAIL, "Olive", "Oneapp"),
            ONE_APP_APPLICATIONS,
        ),
        (_get_or_create_persona(site, NO_APPS_EMAIL, "Noah", "Noapps"), []),
    ]
    for user, wanted in personas:
        click.secho(f"{user.email}", bold=True)
        _seed_applications(site, user, wanted, form, question)
        _register_free_course(site, user, free_course)

        applications = (
            CourseApplication._base_manager.filter(site=site, user=user)
            .select_related("course", "form_progress")
            .order_by("-created_at", "pk")
        )
        click.echo(f"  applications: {applications.count()}")
        for application in applications:
            status = "submitted" if application.is_submitted else "draft"
            click.echo(f"    {application.course.title} [{status}]")
        click.echo(f"  free course: {free_course.title}")
