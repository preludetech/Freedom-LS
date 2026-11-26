"""Seed the DemoDev users a force-delete QA run erases or inspects.

Every user is plain, active, has a verified primary email and the site's
terms and privacy consents, and logs in with its own email as the password
(the DemoDev convention). The superuser is the only staff account.

* ``qa_fd_two_orgs@email.com`` and ``qa_fd_two_orgs_b@email.com``: a ``Learner``
  in two organisations each. Per learner: one membership of a QA cohort that
  has no course registrations (so the membership mints no extra progress
  record), one ``LearnerCourseRegistration``, its ``CourseProgress`` with one
  ``TopicProgress``, and one quiz ``CourseFormAttempt`` whose ``FormProgress``
  holds one ``QuestionAnswer`` carrying a ``QuestionAnswerFile``. Plus one
  standalone, completed ``FormProgress`` no course attempt points at.
* ``qa_fd_applicant@email.com``: a plain user, plus an unclaimed
  ``AnonymousApplicant`` with the same email whose application is submitted.
* ``qa_fd_super@email.com``: superuser and staff.
* ``qa_fd_stale@email.com``: a learner in the educator-facing organisation,
  ``last_active`` 30 days ago, one ``CourseProgress`` last accessed yesterday.
* ``qa_fd_never@email.com``: a learner in the same organisation whose
  ``last_active`` is NULL.

The quiz forms in the demo content have no file-upload question, so the file
hangs off the answer to the quiz's first question.

Idempotent and additive: a row that already exists is reused, never rebuilt.
Flags, password and the two timestamps the stale and never users exist for are
written on every run. The timestamps are written with a queryset ``update()``
after the transaction commits, so no ``auto_now`` field or on-commit receiver
moves them afterwards.

Usage:
    uv run python manage.py qa_create_force_delete_users
"""

from dataclasses import dataclass
from datetime import timedelta
from typing import cast

import djclick as click
from allauth.account.models import EmailAddress

from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import ContentCollectionItem, Course, Topic
from freedom_ls.course_applications.applicant_email import normalise_email
from freedom_ls.course_applications.factories import (
    AnonymousApplicantFactory,
    CourseApplicationFactory,
)
from freedom_ls.course_applications.models import AnonymousApplicant, CourseApplication
from freedom_ls.form_engine.factories import (
    FormProgressFactory,
    QuestionAnswerFactory,
    QuestionAnswerFileFactory,
)
from freedom_ls.form_engine.models import (
    Form,
    FormProgress,
    FormQuestion,
    QuestionAnswer,
    QuestionAnswerFile,
)
from freedom_ls.learner_management.factories import (
    CohortFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
)
from freedom_ls.learner_management.models import (
    Cohort,
    CohortMembership,
    Learner,
    LearnerCourseRegistration,
)
from freedom_ls.learner_management.queries import is_course_open_to_organisation
from freedom_ls.learner_management.utils import ensure_learner
from freedom_ls.learner_progress.factories import (
    CourseFormAttemptFactory,
    TopicProgressFactory,
)
from freedom_ls.learner_progress.models import (
    CourseFormAttempt,
    CourseProgress,
    TopicProgress,
)
from freedom_ls.learner_progress.utils import ensure_course_progress_record
from freedom_ls.organisations.models import Organisation
from freedom_ls.qa_helpers.management.commands.qa_create_clean_applicant import (
    _get_site,
)
from freedom_ls.qa_helpers.management.commands.qa_create_organisation_scenarios import (
    _site_context,
)
from freedom_ls.qa_helpers.management.commands.qa_create_single_org_educator import (
    _ensure_consents,
)
from freedom_ls.qa_helpers.management.commands.qa_create_standalone_form_sitting import (
    _get_form,
    _sit_standalone,
)

SITE_NAME = "DemoDev"
TWO_ORG_EMAILS = ("qa_fd_two_orgs@email.com", "qa_fd_two_orgs_b@email.com")
APPLICANT_EMAIL = "qa_fd_applicant@email.com"
SUPER_EMAIL = "qa_fd_super@email.com"
STALE_EMAIL = "qa_fd_stale@email.com"
NEVER_EMAIL = "qa_fd_never@email.com"

#: The organisation `/educator/` opens on for demodev@email.com (a superuser
#: sees every organisation and lands on the first by name), and a second one.
HOME_ORG_SLUG = "demodev"
SECOND_ORG_SLUG = "harbour-college"
COHORT_NAME = "QA Force Delete Cohort"

#: Its two topics and two quizzes give each organisation its own placements.
TWO_ORG_COURSE_SLUG = "functionality-demo-show-end-with-quiz"
STALE_COURSE_SLUG = "functionality-demo-show-end-with-topic"
STANDALONE_FORM_SLUG = "knowledge-check"
APPLICATION_COURSE_SLUG = "functionality-demo-application-gated-course"

UPLOAD_NAME = "qa-force-delete-upload.txt"
UPLOAD_BYTES = b"QA force-delete upload.\n"
STALE_LAST_ACTIVE_DAYS = 30


@dataclass(frozen=True)
class Placements:
    """One topic and one quiz placement in a course."""

    topic_item: ContentCollectionItem
    quiz_item: ContentCollectionItem


def _ensure_user(email: str, site: Site, *, superuser: bool = False) -> User:
    """Get or create the user, then set flags, password, email and consents."""
    user = User._base_manager.filter(email=email).first()
    if user is None:
        user = cast(User, UserFactory(email=email, site=site, superuser=superuser))
    else:
        user.site = site
        user.is_active = True
        user.is_staff = superuser
        user.is_superuser = superuser
        user.set_password(email)
        user.save()
    EmailAddress.objects.update_or_create(
        user=user, email=email, defaults={"verified": True, "primary": True}
    )
    _ensure_consents(site, user)
    return user


def _get_organisation(site: Site, slug: str) -> Organisation:
    organisation = Organisation._base_manager.filter(site=site, slug=slug).first()
    if organisation is None:
        raise click.ClickException(f"No organisation '{slug}' on site '{site.name}'.")
    return organisation


def _get_course(site: Site, slug: str, organisations: list[Organisation]) -> Course:
    course = Course._base_manager.filter(site=site, slug=slug).first()
    if course is None:
        raise click.ClickException(f"No course '{slug}' on site '{site.name}'.")
    for organisation in organisations:
        if not is_course_open_to_organisation(course, organisation):
            raise click.ClickException(
                f"Course '{slug}' is not open to organisation '{organisation.slug}'."
            )
    return course


def _placements(course: Course, count: int) -> list[Placements]:
    """The course's first `count` topic and quiz placements, paired in order."""
    items = ContentCollectionItem._base_manager.filter(
        collection_type=ContentType.objects.get_for_model(Course),
        collection_id=course.pk,
    ).order_by("order")
    topic_type = ContentType.objects.get_for_model(Topic)
    form_type = ContentType.objects.get_for_model(Form)
    topics = [item for item in items if item.child_type_id == topic_type.pk]
    quizzes = [item for item in items if item.child_type_id == form_type.pk]
    if len(topics) < count or len(quizzes) < count:
        raise click.ClickException(
            f"Course '{course.slug}' needs {count} topic and {count} quiz placements."
        )
    return [Placements(topics[i], quizzes[i]) for i in range(count)]


def _ensure_cohort(site: Site, organisation: Organisation) -> Cohort:
    cohort = Cohort._base_manager.filter(
        site=site, organisation=organisation, name=COHORT_NAME
    ).first()
    if cohort is None:
        cohort = cast(
            Cohort,
            CohortFactory(site=site, organisation=organisation, name=COHORT_NAME),
        )
    return cohort


def _ensure_registration(learner: Learner, course: Course) -> CourseProgress:
    """The learner's registration and its record, minted now rather than on commit."""
    registration = LearnerCourseRegistration._base_manager.filter(
        learner=learner, course=course
    ).first()
    if registration is None:
        registration = cast(
            LearnerCourseRegistration,
            LearnerCourseRegistrationFactory(
                learner=learner,
                course=course,
                site=learner.site,
                is_active=True,
                self_registered=True,
            ),
        )
    return ensure_course_progress_record(learner, course, registration)


def _ensure_quiz_attempt(
    record: CourseProgress, item: ContentCollectionItem, site: Site
) -> CourseFormAttempt:
    """One attempt at the placed quiz whose first answer carries a file."""
    attempt = (
        CourseFormAttempt._base_manager.filter(course_progress=record)
        .select_related("form_progress")
        .first()
    )
    if attempt is None:
        attempt = cast(
            CourseFormAttempt,
            CourseFormAttemptFactory(
                site=site,
                course_progress=record,
                collection_item=item,
                form=item.child,
            ),
        )
    sitting = attempt.form_progress
    answer = QuestionAnswer._base_manager.filter(form_progress=sitting).first()
    if answer is None:
        question = (
            FormQuestion._base_manager.filter(form_page__form_id=sitting.form_id)
            .order_by("form_page__order", "order")
            .first()
        )
        if question is None:
            raise click.ClickException(f"Form '{sitting.form}' has no questions.")
        answer = cast(
            QuestionAnswer,
            QuestionAnswerFactory(form_progress=sitting, question=question, site=site),
        )
        correct = question.options.filter(correct=True)
        answer.selected_options.set(correct or question.options.order_by("order")[:1])
    if not QuestionAnswerFile._base_manager.filter(answer=answer).exists():
        QuestionAnswerFileFactory(
            answer=answer,
            site=site,
            original_filename=UPLOAD_NAME,
            file=ContentFile(UPLOAD_BYTES, name=UPLOAD_NAME),
        )
    return attempt


def _ensure_enrolment(
    user: User,
    organisation: Organisation,
    course: Course,
    placements: Placements,
    site: Site,
) -> Learner:
    learner = ensure_learner(user, organisation)
    cohort = _ensure_cohort(site, organisation)
    if not CohortMembership._base_manager.filter(
        learner=learner, cohort=cohort
    ).exists():
        CohortMembershipFactory(learner=learner, cohort=cohort, site=site)
    record = _ensure_registration(learner, course)
    if not TopicProgress._base_manager.filter(course_progress=record).exists():
        TopicProgressFactory(
            site=site,
            course_progress=record,
            collection_item=placements.topic_item,
            topic=placements.topic_item.child,
        )
    _ensure_quiz_attempt(record, placements.quiz_item, site)
    return learner


def _ensure_standalone_sitting(user: User, form: Form, site: Site) -> FormProgress:
    sitting = FormProgress._base_manager.filter(
        user=user, course_attempt__isnull=True
    ).first()
    return sitting or _sit_standalone(user, form, site)


def _ensure_anonymous_application(site: Site, email: str) -> CourseApplication:
    """An unclaimed applicant for `email` with a submitted application."""
    course = _get_course(site, APPLICATION_COURSE_SLUG, [])
    if course.application_form is None:
        raise click.ClickException(f"Course '{course.slug}' has no application form.")
    applicant = AnonymousApplicant._base_manager.filter(
        email=normalise_email(email), course=course, claimed_at__isnull=True
    ).first()
    if applicant is None:
        applicant = cast(
            AnonymousApplicant,
            AnonymousApplicantFactory(
                site=site,
                course=course,
                email=normalise_email(email),
                first_name="Quinn",
                last_name="Applicant",
                consented_at=timezone.now(),
            ),
        )
    application = CourseApplication._base_manager.filter(
        anonymous_applicant=applicant
    ).first()
    if application is None:
        sitting = cast(
            FormProgress,
            FormProgressFactory(user=None, form=course.application_form, site=site),
        )
        sitting.completed_time = timezone.now()
        sitting.save(update_fields=["completed_time"])
        application = cast(
            CourseApplication,
            CourseApplicationFactory(
                site=site,
                user=None,
                anonymous_applicant=applicant,
                course=course,
                form_progress=sitting,
                state=CourseApplication.State.SUBMITTED,
                submitted_at=sitting.completed_time,
            ),
        )
    return application


def _count_line(user: User) -> str:
    learners = Learner._base_manager.filter(user=user)
    counts = {
        "Learner": learners.count(),
        "CohortMembership": CohortMembership._base_manager.filter(
            learner__in=learners
        ).count(),
        "LearnerCourseRegistration": LearnerCourseRegistration._base_manager.filter(
            learner__in=learners
        ).count(),
        "CourseProgress": CourseProgress._base_manager.filter(
            learner__in=learners
        ).count(),
        "TopicProgress": TopicProgress._base_manager.filter(
            course_progress__learner__in=learners
        ).count(),
        "CourseFormAttempt": CourseFormAttempt._base_manager.filter(
            course_progress__learner__in=learners
        ).count(),
        "FormProgress": FormProgress._base_manager.filter(user=user).count(),
        "FormProgress(standalone)": FormProgress._base_manager.filter(
            user=user, course_attempt__isnull=True
        ).count(),
        "QuestionAnswer": QuestionAnswer._base_manager.filter(
            form_progress__user=user
        ).count(),
        "QuestionAnswerFile": QuestionAnswerFile._base_manager.filter(
            answer__form_progress__user=user
        ).count(),
    }
    return " ".join(f"{name}={count}" for name, count in counts.items())


def _learner_lines(user: User) -> list[str]:
    return [
        f"Learner {learner.pk} organisation={learner.organisation.name} "
        f"({learner.organisation.slug})"
        for learner in Learner._base_manager.filter(user=user)
        .select_related("organisation")
        .order_by("organisation__name")
    ]


@click.command()
def command() -> None:
    """Create or top up the force-delete QA users on DemoDev."""
    site = _get_site(SITE_NAME)
    home = _get_organisation(site, HOME_ORG_SLUG)
    second = _get_organisation(site, SECOND_ORG_SLUG)
    two_org_course = _get_course(site, TWO_ORG_COURSE_SLUG, [home, second])
    stale_course = _get_course(site, STALE_COURSE_SLUG, [home])
    placements = _placements(two_org_course, 2)
    standalone_form = _get_form(STANDALONE_FORM_SLUG, site)

    with _site_context(site), transaction.atomic():
        two_org_users = []
        for email in TWO_ORG_EMAILS:
            user = _ensure_user(email, site)
            for organisation, placement in zip((home, second), placements, strict=True):
                _ensure_enrolment(user, organisation, two_org_course, placement, site)
            _ensure_standalone_sitting(user, standalone_form, site)
            two_org_users.append(user)

        applicant = _ensure_user(APPLICANT_EMAIL, site)
        application = _ensure_anonymous_application(site, APPLICANT_EMAIL)

        superuser = _ensure_user(SUPER_EMAIL, site, superuser=True)

        stale = _ensure_user(STALE_EMAIL, site)
        stale_learner = ensure_learner(stale, home)
        stale_record = _ensure_registration(stale_learner, stale_course)

        never = _ensure_user(NEVER_EMAIL, site)
        never_learner = ensure_learner(never, home)

    # After commit: nothing queued on commit can move these again.
    now = timezone.now()
    User._base_manager.filter(pk=stale.pk).update(
        last_active=now - timedelta(days=STALE_LAST_ACTIVE_DAYS)
    )
    CourseProgress._base_manager.filter(pk=stale_record.pk).update(
        last_accessed_time=now - timedelta(days=1)
    )
    User._base_manager.filter(pk=never.pk).update(last_active=None)

    click.secho(f"\nSite: {site.name} ({site.domain}) [id {site.pk}]", fg="cyan")
    click.secho("Password for every user = its email address", fg="cyan")
    for user in two_org_users:
        click.secho(f"\n== {user.email} (user pk {user.pk}) ==", fg="green", bold=True)
        for line in _learner_lines(user):
            click.echo(f"  {line}")
        click.echo(f"  {_count_line(user)}")

    applicant_row = application.anonymous_applicant
    click.secho(
        f"\n== {APPLICANT_EMAIL} (user pk {applicant.pk}) ==", fg="green", bold=True
    )
    click.echo(
        f"  AnonymousApplicant {applicant_row.pk if applicant_row else None} "
        f"claimed_at={applicant_row.claimed_at if applicant_row else None} "
        f"user={applicant_row.user_id if applicant_row else None}"
    )
    click.echo(
        f"  CourseApplication {application.pk} state={application.state} "
        f"course={application.course.slug} form_progress={application.form_progress_id}"
    )

    superuser.refresh_from_db()
    click.secho(
        f"\n== {SUPER_EMAIL} (user pk {superuser.pk}) ==", fg="green", bold=True
    )
    click.echo(f"  is_staff={superuser.is_staff} is_superuser={superuser.is_superuser}")

    stale.refresh_from_db()
    stale_record.refresh_from_db()
    click.secho(f"\n== {STALE_EMAIL} (user pk {stale.pk}) ==", fg="green", bold=True)
    click.echo(f"  Learner {stale_learner.pk} organisation={home.name} ({home.slug})")
    click.echo(f"  last_active={stale.last_active}")
    click.echo(
        f"  CourseProgress {stale_record.pk} course={stale_course.slug} "
        f"last_accessed_time={stale_record.last_accessed_time}"
    )

    never.refresh_from_db()
    click.secho(f"\n== {NEVER_EMAIL} (user pk {never.pk}) ==", fg="green", bold=True)
    click.echo(f"  Learner {never_learner.pk} organisation={home.name} ({home.slug})")
    click.echo(f"  last_active={never.last_active}")
