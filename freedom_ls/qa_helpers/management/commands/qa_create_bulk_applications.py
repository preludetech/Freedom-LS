"""Create forty submitted applications to the demo gated course, for export QA.

Creates (idempotently) on a single site (default: DemoDev):

- Forty users ``qa_bulk_01@email.com`` ... ``qa_bulk_40@email.com`` (password
  equals the email, verified+primary allauth EmailAddress, a Learner in the
  site's default organisation).
- For each, a submitted CourseApplication to "Functionality Demo - Application
  gated course" whose completed FormProgress sitting of the course's
  application form holds exactly two answers: the full-name question
  ("Bulk Applicant NN") and the date-of-birth question (1990-01-01 + NN days).
  Every other question is left unanswered.

Existing users, applications and forms are only read, never modified.
"""

from datetime import date, timedelta
from typing import cast

import djclick as click
from allauth.account.models import EmailAddress

from django.contrib.sites.models import Site
from django.db import transaction
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import Course
from freedom_ls.course_applications.factories import CourseApplicationFactory
from freedom_ls.course_applications.models import CourseApplication
from freedom_ls.form_engine.factories import (
    FormProgressFactory,
    QuestionAnswerFactory,
)
from freedom_ls.form_engine.models import FormProgress, FormQuestion, QuestionAnswer
from freedom_ls.learner_management.factories import LearnerFactory
from freedom_ls.organisations.utils import get_default_organisation

COURSE_SLUG = "functionality-demo-application-gated-course"
NAME_QUESTION = "What is your full name?"
DOB_QUESTION = "What is your date of birth?"
COUNT = 40
BASE_DOB = date(1990, 1, 1)


def _email(n: int) -> str:
    return f"qa_bulk_{n:02d}@email.com"


def _get_or_create_user(site: Site, n: int) -> tuple[User, bool]:
    email = _email(n)
    user: User | None = User._base_manager.filter(email__iexact=email).first()
    if user is not None:
        return user, False
    created = cast(
        User,
        UserFactory(
            email=email,
            first_name="Bulk",
            last_name=f"Applicant {n:02d}",
            is_active=True,
            password=email,
            site=site,
        ),
    )
    return created, True


def _question(course: Course, text: str) -> FormQuestion:
    question: FormQuestion | None = FormQuestion.objects.filter(
        form_page__form=course.application_form, question=text
    ).first()
    if question is None:
        raise click.ClickException(f"Question {text!r} not found on the form.")
    return question


def _ensure_application(
    site: Site,
    user: User,
    course: Course,
    answers: list[tuple[FormQuestion, str]],
) -> CourseApplication:
    application: CourseApplication | None = (
        CourseApplication.objects.filter(user=user, course=course, site=site)
        .select_related("form_progress")
        .first()
    )
    if application is None:
        sitting = cast(
            FormProgress,
            FormProgressFactory(
                user=user,
                form=course.application_form,
                completed_time=timezone.now(),
                furthest_page_reached=1,
                site=site,
            ),
        )
        application = cast(
            CourseApplication,
            CourseApplicationFactory(
                user=user, course=course, form_progress=sitting, site=site
            ),
        )
    sitting_or_none = application.form_progress
    if sitting_or_none is None:
        raise click.ClickException(
            f"Application {application.pk} has no form sitting; reset it first."
        )
    if sitting_or_none.completed_time is None:
        sitting_or_none.completed_time = timezone.now()
        sitting_or_none.save(update_fields=["completed_time"])
    for question, text in answers:
        answer: QuestionAnswer | None = QuestionAnswer.objects.filter(
            form_progress=sitting_or_none, question=question
        ).first()
        if answer is None:
            QuestionAnswerFactory(
                form_progress=sitting_or_none,
                question=question,
                text_answer=text,
                site=site,
            )
        elif answer.text_answer != text:
            answer.text_answer = text
            answer.save(update_fields=["text_answer"])
    return cast(
        CourseApplication,
        CourseApplication.objects.select_related("form_progress").get(
            pk=application.pk
        ),
    )


@click.command()
@click.argument("site_name", default="DemoDev")
def command(site_name: str) -> None:
    """Create forty bulk applicants with submitted applications.

    SITE_NAME is the site to create data on (default: DemoDev).
    """
    try:
        site = Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        available = list(Site.objects.values_list("name", flat=True))
        raise click.ClickException(
            f"Site '{site_name}' not found. Available: {available}"
        ) from e
    course: Course | None = (
        Course.objects.filter(slug=COURSE_SLUG, site=site)
        .select_related("application_form")
        .first()
    )
    if course is None or course.application_form is None:
        raise click.ClickException(
            f"Course {COURSE_SLUG} with an application form not found."
        )
    name_question = _question(course, NAME_QUESTION)
    dob_question = _question(course, DOB_QUESTION)
    organisation = get_default_organisation(site)

    created_count = 0
    applications: list[CourseApplication] = []
    with transaction.atomic():
        for n in range(1, COUNT + 1):
            user, created = _get_or_create_user(site, n)
            created_count += int(created)
            EmailAddress.objects.update_or_create(
                user=user,
                email=user.email,
                defaults={"verified": True, "primary": True},
            )
            LearnerFactory(user=user, organisation=organisation, site=site)
            dob = (BASE_DOB + timedelta(days=n)).isoformat()
            applications.append(
                _ensure_application(
                    site,
                    user,
                    course,
                    [
                        (name_question, f"Bulk Applicant {n:02d}"),
                        (dob_question, dob),
                    ],
                )
            )

    submitted = sum(1 for a in applications if a.is_submitted)
    answer_counts = {
        QuestionAnswer.objects.filter(form_progress=a.form_progress).count()
        for a in applications
    }
    click.secho(f"Site: {site.name} ({site.domain})", fg="cyan")
    click.secho(f"Users created this run: {created_count}", fg="green")
    click.secho(
        f"Bulk applications: {len(applications)}  is_submitted=True: {submitted}  "
        f"answers per sitting: {sorted(answer_counts)}",
        fg="green" if submitted == COUNT and answer_counts == {2} else "red",
    )
    click.secho(
        f"Applications on '{course.title}': "
        f"{CourseApplication.objects.filter(course=course, site=site).count()}",
        fg="green",
    )
    click.secho(
        f"CourseApplication total on {site.name}: "
        f"{CourseApplication.objects.filter(site=site).count()}",
        fg="green",
    )
    click.secho(f"Logins: {_email(1)} ... {_email(COUNT)}, password = email")
