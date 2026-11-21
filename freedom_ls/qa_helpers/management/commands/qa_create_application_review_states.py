"""Seed applications in every review state for the application-review QA walkthrough.

Idempotently writes, on one site (default: DemoDev):

* Seven published, application-gated QA courses:
  F1-F5 and G each name the shared three-page "QA review states form";
  N names no application form.
* ``qa_review_applicant_a@email.com`` holds exactly two submitted applications,
  on F1 and F2, and nothing else.
* ``qa_review_applicant_b@email.com`` holds exactly three applications:
  approved on F3, rejected on F4 (created after F3's, with a two-line message
  carrying a script tag, to check escaping), and a draft on F5 whose sitting
  has one of its three answers saved and is not completed.
* Nobody has applied to G: every application on G, anonymous ones included,
  is deleted on each run, so a tester can apply there anonymously.

Every state change goes through ``course_applications.transitions``, so
approve and reject write their audit entries. The reviewer acting on them is
``demodev@email.com`` (``is_staff``; created by ``create_demo_data``).

Re-running is destructive for what it owns: both applicants' applications,
sittings, registrations and memberships, and every application on G.

DemoDev-only convention: each applicant's password is their own email address.

``--reject-pk <pk> --message <text>`` seeds nothing: it rejects that one
submitted application (anonymous ones included) through ``reject_application``
with the same reviewer, so the audit entry exists.

Usage:
    uv run python manage.py qa_create_application_review_states
    uv run python manage.py qa_create_application_review_states --site-name DemoDev
    uv run python manage.py qa_create_application_review_states \
        --reject-pk <pk> --message "Not this time."
"""

from dataclasses import dataclass
from typing import cast

import djclick as click

from django.contrib.sites.models import Site
from django.db import transaction
from django.urls import reverse

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import Course, CourseVisibility
from freedom_ls.course_applications.exceptions import (
    ApplicationStateError,
    RejectionMessageError,
)
from freedom_ls.course_applications.factories import CourseApplicationFactory
from freedom_ls.course_applications.models import (
    AnonymousApplicant,
    CourseApplication,
)
from freedom_ls.course_applications.transitions import (
    approve_application,
    reject_application,
    submit_application,
)
from freedom_ls.form_engine.enums import QuestionType
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormProgressFactory,
    FormQuestionFactory,
    QuestionAnswerFactory,
)
from freedom_ls.form_engine.models import (
    Form,
    FormPage,
    FormProgress,
    FormQuestion,
    FormStrategy,
)
from freedom_ls.learner_management.utils import ensure_learner
from freedom_ls.organisations.utils import get_default_organisation
from freedom_ls.qa_helpers.management.commands.qa_create_application_review_accounts import (
    _ensure_user,
    _ensure_verified_email,
    _purge_course_data,
)

APPLICANT_A_EMAIL = "qa_review_applicant_a@email.com"
APPLICANT_B_EMAIL = "qa_review_applicant_b@email.com"
REVIEWER_EMAIL = "demodev@email.com"

REJECTION_MESSAGE = (
    "Thanks for applying.\n"
    "We need more detail about your experience.<script>alert(1)</script>"
)

FORM_SLUG = "qa-review-states-form"
FORM_TITLE = "QA review states form"
# (page order, page title, question text), one question per page.
FORM_PAGES = [
    (1, "About you", "What is your full name?"),
    (2, "Your experience", "Describe your relevant experience."),
    (3, "Your goals", "What do you hope to gain from the course?"),
]


@dataclass(frozen=True)
class SeededCourse:
    label: str
    title: str
    slug: str
    has_form: bool


COURSES = [
    SeededCourse("F1", "QA Review F1 Submitted A", "qa-review-f1", True),
    SeededCourse("F2", "QA Review F2 Submitted A", "qa-review-f2", True),
    SeededCourse("F3", "QA Review F3 Approved B", "qa-review-f3", True),
    SeededCourse("F4", "QA Review F4 Rejected B", "qa-review-f4", True),
    SeededCourse("F5", "QA Review F5 Draft B", "qa-review-f5", True),
    SeededCourse("G", "QA Review G Open To Anonymous", "qa-review-g", True),
    SeededCourse("N", "QA Review N No Form", "qa-review-n", False),
]


def _get_site(site_name: str) -> Site:
    try:
        return Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        available = list(Site.objects.values_list("name", flat=True))
        raise click.ClickException(
            f"Site '{site_name}' not found. Available: {available}. "
            "Run `manage.py create_demo_data --yes` first."
        ) from e


def _ensure_form(site: Site) -> tuple[Form, list[FormQuestion]]:
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
    questions: list[FormQuestion] = []
    for order, page_title, text in FORM_PAGES:
        page: FormPage | None = FormPage._base_manager.filter(
            form=form, order=order
        ).first()
        if page is None:
            page = cast(
                FormPage,
                FormPageFactory(
                    form=form,
                    title=page_title,
                    slug=f"{FORM_SLUG}-page-{order}",
                    order=order,
                    site=site,
                ),
            )
        question: FormQuestion | None = FormQuestion._base_manager.filter(
            form_page=page, question=text
        ).first()
        if question is None:
            question = cast(
                FormQuestion,
                FormQuestionFactory(
                    form_page=page,
                    question=text,
                    type=QuestionType.SHORT_TEXT,
                    order=1,
                    required=True,
                    site=site,
                ),
            )
        questions.append(question)
    return form, questions


def _ensure_course(site: Site, seeded: SeededCourse, form: Form) -> Course:
    fields = {
        "title": seeded.title,
        "description": f"{seeded.title}: an application-gated QA course.",
        "access_config": {"access_type": "application_gated"},
        "visibility": CourseVisibility.PUBLISHED,
        "application_form": form if seeded.has_form else None,
    }
    course: Course | None = Course._base_manager.filter(
        slug=seeded.slug, site=site
    ).first()
    if course is None:
        return cast(Course, CourseFactory(slug=seeded.slug, site=site, **fields))
    for name, value in fields.items():
        setattr(course, name, value)
    course.save(update_fields=list(fields))
    return course


def _clear_course_applications(course: Course) -> None:
    """Delete every application on the course, then its sitting (RESTRICT order),
    then any anonymous applicant left behind."""
    for application in CourseApplication._base_manager.filter(course=course):
        sitting_pk = application.form_progress_id
        click.echo(
            f"  removing {application} state={application.state} "
            f"course={course.slug} -> {application.delete()}"
        )
        if sitting_pk is not None:
            result = FormProgress._base_manager.filter(pk=sitting_pk).delete()
            click.echo(f"    FormProgress.delete() -> {result}")
    leftovers = AnonymousApplicant._base_manager.filter(course=course)
    if leftovers.exists():
        click.echo(f"  AnonymousApplicant.delete() -> {leftovers.delete()}")


def _ensure_applicant(site: Site, email: str, first: str, last: str) -> User:
    user, _created = _ensure_user(email, site, is_staff=False)
    user.first_name = first
    user.last_name = last
    user.save(update_fields=["first_name", "last_name"])
    _ensure_verified_email(user)
    ensure_learner(user, get_default_organisation(site))
    user.user_permissions.clear()
    user.groups.clear()
    removed = {name: n for name, n in _purge_course_data(user).items() if n}
    if removed:
        click.secho(f"  {email}: removed {removed}", fg="red")
    return user


def _start(
    site: Site,
    user: User,
    course: Course,
    answers: list[tuple[FormQuestion, str]],
    furthest_page: FormPage,
) -> CourseApplication:
    """A draft application whose open sitting holds the given answers."""
    form = cast(Form, course.application_form)
    sitting = cast(
        FormProgress,
        FormProgressFactory(
            user=user, form=form, furthest_page=furthest_page, site=site
        ),
    )
    for question, text in answers:
        QuestionAnswerFactory(
            form_progress=sitting, question=question, text_answer=text, site=site
        )
    return cast(
        CourseApplication,
        CourseApplicationFactory(
            user=user, course=course, form_progress=sitting, site=site
        ),
    )


def _submitted(
    site: Site, user: User, course: Course, questions: list[FormQuestion]
) -> CourseApplication:
    """An application submitted through its completed sitting."""
    texts = [
        f"{user.first_name} {user.last_name}",
        f"Five years relevant to {course.title}.",
        "A clearer grasp of the subject.",
    ]
    application = _start(
        site,
        user,
        course,
        list(zip(questions, texts, strict=True)),
        furthest_page=questions[-1].form_page,
    )
    cast(FormProgress, application.form_progress).complete()
    return submit_application(application)


def _echo_courses(courses: dict[str, Course]) -> None:
    click.secho("== Courses ==", fg="cyan", bold=True)
    for seeded in COURSES:
        course = courses[seeded.label]
        detail = reverse(
            "learner_interface:course_detail", kwargs={"course_slug": course.slug}
        )
        count = CourseApplication._base_manager.filter(course=course).count()
        click.echo(
            f"  {seeded.label}: '{course.title}' slug={course.slug} "
            f"form={'yes' if course.application_form_id else 'none'} "
            f"visibility={course.visibility} applications={count} detail={detail}"
        )


def _echo_applications(user: User) -> None:
    click.secho(f"  {user.email} (pk={user.pk})", bold=True)
    applications = (
        CourseApplication._base_manager.filter(user=user)
        .select_related("course", "form_progress")
        .order_by("created_at")
    )
    for application in applications:
        status = reverse("course_applications:status", kwargs={"pk": application.pk})
        first_page = reverse(
            "course_applications:form_page",
            kwargs={"pk": application.pk, "page_number": 1},
        )
        sitting = application.form_progress
        answers = sitting.answers.count() if sitting is not None else 0
        completed = sitting.completed_time is not None if sitting else None
        click.echo(
            f"    {application.course.slug}: pk={application.pk} "
            f"state={application.state} created_at={application.created_at.isoformat()} "
            f"answers={answers} sitting_completed={completed}"
        )
        click.echo(f"      status={status} first_form_page={first_page}")
        if application.rejection_message:
            click.echo(f"      rejection_message={application.rejection_message!r}")


def _get_reviewer() -> User:
    reviewer: User | None = User._base_manager.filter(email=REVIEWER_EMAIL).first()
    if reviewer is None or not reviewer.is_staff:
        raise click.ClickException(
            f"Staff user {REVIEWER_EMAIL} not found. "
            "Run `manage.py create_demo_data --yes` first."
        )
    return reviewer


def _reject_one(pk: str, message: str, reviewer: User) -> None:
    """Reject one submitted application through the transition, and show it."""
    application: CourseApplication | None = (
        CourseApplication._base_manager.select_related("course", "user")
        .filter(pk=pk)
        .first()
    )
    if application is None:
        raise click.ClickException(f"No CourseApplication with pk={pk}.")
    who = application.user.email if application.user else "anonymous (unclaimed)"
    click.echo(
        f"Rejecting {application} pk={application.pk} course={application.course.slug} "
        f"applicant={who} site_id={application.site_id} state={application.state}"
    )
    try:
        reject_application(application, actor=reviewer, message=message)
    except (ApplicationStateError, RejectionMessageError) as e:
        raise click.ClickException(f"Refused: {e!r}") from e
    status = reverse("course_applications:status", kwargs={"pk": application.pk})
    click.secho(
        f"Now state={application.state} decided_at={application.decided_at} "
        f"rejection_message={application.rejection_message!r} status={status}",
        fg="green",
    )


@click.command()
@click.option("--site-name", default="DemoDev", show_default=True)
@click.option("--reject-pk", default=None, help="Only reject this application.")
@click.option("--message", default=None, help="Rejection message for --reject-pk.")
def command(site_name: str, reject_pk: str | None, message: str | None) -> None:
    """Seed applicants A and B, courses F1-F5, G and N."""
    reviewer = _get_reviewer()
    if reject_pk is not None:
        if not message:
            raise click.ClickException("--reject-pk needs --message.")
        _reject_one(reject_pk, message, reviewer)
        return
    if message is not None:
        raise click.ClickException("--message is only used with --reject-pk.")
    site = _get_site(site_name)

    with transaction.atomic():
        form, questions = _ensure_form(site)
        courses = {c.label: _ensure_course(site, c, form) for c in COURSES}
        user_a = _ensure_applicant(site, APPLICANT_A_EMAIL, "Ada", "ReviewA")
        user_b = _ensure_applicant(site, APPLICANT_B_EMAIL, "Ben", "ReviewB")
        _clear_course_applications(courses["G"])

        _submitted(site, user_a, courses["F1"], questions)
        _submitted(site, user_a, courses["F2"], questions)

        approve_application(
            _submitted(site, user_b, courses["F3"], questions), actor=reviewer
        )
        reject_application(
            _submitted(site, user_b, courses["F4"], questions),
            actor=reviewer,
            message=REJECTION_MESSAGE,
        )
        _start(
            site,
            user_b,
            courses["F5"],
            [(questions[0], "Ben ReviewB")],
            furthest_page=questions[0].form_page,
        )

    click.secho(f"Site: {site.name} (id={site.pk}, {site.domain})", fg="cyan")
    click.secho(f"Reviewer (audit actor): {reviewer.email}", fg="cyan")
    click.secho("Password for each applicant: their own email address", fg="cyan")
    click.echo("")
    _echo_courses(courses)
    click.echo("")
    click.secho("== Applications ==", fg="cyan", bold=True)
    _echo_applications(user_a)
    _echo_applications(user_b)
