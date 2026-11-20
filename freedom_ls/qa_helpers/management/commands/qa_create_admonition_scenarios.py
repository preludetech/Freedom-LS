"""Seed the callout/admonition QA run (misure-of-admonitions).

On the named site (default DemoDev), idempotently:

1. ``content-widgets-demo-reference``: ``table_of_contents_in_development = True``.
2. ``demodev@email.com`` as a learner of the default organisation (``demodev``):

   - ``functionality-demo-course-parts``: individual registration whose record holds an
     open pause started 2 days ago with a planned resume 14 days from today;
   - ``functionality-demo-show-end-with-topic``: individual registration with access
     ending ON (``outline_and_results``) and a fixed whole-course time limit 10 days ago,
     so access has ended;
   - ``functionality-demo-show-end-with-quiz``: individual registration with item 1
     completed, so item 2 (the "Mid course Quiz", every question required) is ready.

3. Organisation ``QA Solo Org`` (``qa-solo-org``) whose only staff member and only
   organisation admin is ``demodev@email.com``.
4. In ``demodev``: cohort ``QA Delete Cascade Cohort`` (empty, with a deadline config
   and a messaging config, so its delete dialog lists dependents) and cohort
   ``QA Delete Blocked Cohort`` (empty, for the two-tab blocked-delete race).
5. In ``demodev``: cohorts ``QA Move Source`` (holding ``qa-move-learner@email.com``)
   and ``QA Move Destination`` (empty), for the refused-move race.

The QA login's password is never touched. The move learner's password is
``testpass123``.

Usage:
    uv run python manage.py qa_create_admonition_scenarios [--site-name DemoDev]
"""

from datetime import timedelta
from typing import cast

import djclick as click
from allauth.account.models import EmailAddress

from django.contrib.sites.models import Site
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import Course, Topic
from freedom_ls.deadlines.actions import pause_course
from freedom_ls.deadlines.models import (
    AfterAccessEnded,
    CohortDeadlineConfig,
    CoursePause,
    DeadlineKind,
    DeadlineSwitch,
    LearnerCourseRegistrationDeadlineConfig,
    LearnerDeadlineOverride,
)
from freedom_ls.learner_management.factories import (
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import (
    CohortMembership,
    Learner,
    LearnerCourseRegistration,
    StaffMember,
)
from freedom_ls.learner_management.utils import ensure_staff_member
from freedom_ls.learner_progress.factories import CourseProgressFactory
from freedom_ls.learner_progress.models import CourseProgress, TopicProgress
from freedom_ls.messaging_policy.models import CohortMessagingConfig
from freedom_ls.organisations.models import Organisation
from freedom_ls.organisations.utils import get_default_organisation
from freedom_ls.qa_helpers.management.commands.qa_create_cohort_administration_scenario import (
    _ensure_cohort,
    _ensure_organisation,
)
from freedom_ls.qa_helpers.management.commands.qa_create_organisation_scenarios import (
    _pin_current_site,
    _site_context,
)
from freedom_ls.role_based_permissions.models import ObjectRoleAssignment
from freedom_ls.role_based_permissions.utils import assign_object_role

QA_LOGIN = "demodev@email.com"
PAUSED_SLUG = "functionality-demo-course-parts"
ENDED_SLUG = "functionality-demo-show-end-with-topic"
QUIZ_SLUG = "functionality-demo-show-end-with-quiz"
SOLO_ORG_NAME = "QA Solo Org"
SOLO_ORG_SLUG = "qa-solo-org"
CASCADE_COHORT = "QA Delete Cascade Cohort"
BLOCKED_COHORT = "QA Delete Blocked Cohort"
MOVE_SOURCE = "QA Move Source"
MOVE_DESTINATION = "QA Move Destination"
MOVE_LEARNER_EMAIL = "qa-move-learner@email.com"
MOVE_LEARNER_PASSWORD = "testpass123"  # noqa: S105  # pragma: allowlist secret  # dev-only QA credential
SEED_REASON = "QA seed: admonitions"


def _course(site: Site, slug: str) -> Course:
    course = Course._base_manager.filter(site=site, slug=slug).first()
    if course is None:
        raise click.ClickException(
            f"Course '{slug}' not on {site.name}; run content_save demo_content {site.name}."
        )
    return course


def _learner(user: User, organisation: Organisation, site: Site) -> Learner:
    learner = Learner._base_manager.filter(user=user, organisation=organisation).first()
    if learner is None:
        learner = cast(
            Learner, LearnerFactory(user=user, organisation=organisation, site=site)
        )
    return learner


def _registration_and_record(
    learner: Learner, course: Course, site: Site
) -> tuple[LearnerCourseRegistration, CourseProgress]:
    registration = LearnerCourseRegistration._base_manager.filter(
        learner=learner, course=course
    ).first()
    if registration is None:
        registration = cast(
            LearnerCourseRegistration,
            LearnerCourseRegistrationFactory(
                site=site, learner=learner, course=course, is_active=True
            ),
        )
    elif not registration.is_active:
        registration.is_active = True
        registration.save()
    record = CourseProgress._base_manager.filter(
        learner=learner, course=course, learner_registration=registration
    ).first()
    if record is None:
        record = cast(
            CourseProgress,
            CourseProgressFactory(
                site=site,
                learner=learner,
                course=course,
                learner_registration=registration,
            ),
        )
    return registration, record


def _ensure_widgets_toc(site: Site) -> None:
    course = _course(site, "content-widgets-demo-reference")
    old = course.table_of_contents_in_development
    Course._base_manager.filter(pk=course.pk).update(
        table_of_contents_in_development=True
    )
    click.echo(
        f"[1] {course.title} ({course.slug}): table_of_contents_in_development "
        f"{old} -> True"
    )


def _ensure_paused(record: CourseProgress, actor: User) -> CoursePause:
    now = timezone.now()
    today = timezone.localdate()
    existing = CoursePause._base_manager.filter(
        course_progress=record, ended_at__isnull=True
    ).first()
    if (
        existing is not None
        and existing.planned_resume_on is not None
        and existing.planned_resume_on > today
    ):
        click.echo(
            f"[2a] Already paused: {existing} (resume {existing.planned_resume_on})"
        )
        return existing
    if existing is not None:
        click.echo(f"[2a] Replacing stale pause {existing.pk}: {existing.delete()}")
    pause = pause_course(
        record,
        actor=actor,
        reason=SEED_REASON,
        planned_resume_on=today + timedelta(days=14),
        now=now - timedelta(days=2),
    )
    click.echo(f"[2a] Paused: {pause} (resume {pause.planned_resume_on})")
    return pause


def _ensure_ended(
    registration: LearnerCourseRegistration, record: CourseProgress, site: Site
) -> None:
    LearnerCourseRegistrationDeadlineConfig._base_manager.update_or_create(
        learner_registration=registration,
        defaults={
            "site": site,
            "end_course_access": DeadlineSwitch.ON,
            "after_access_ended": AfterAccessEnded.OUTLINE_AND_RESULTS,
        },
    )
    LearnerDeadlineOverride._base_manager.filter(
        course_progress=record, collection_item__isnull=True
    ).delete()
    due = timezone.localdate() - timedelta(days=10)
    LearnerDeadlineOverride._base_manager.create(
        site=site,
        course_progress=record,
        collection_item=None,
        kind=DeadlineKind.FIXED,
        due_date=due,
    )
    click.echo(f"[2b] Access ending ON, course time limit fixed at {due}")


def _ensure_quiz_ready(record: CourseProgress, course: Course, site: Site) -> None:
    item = next(iter(course.viewable_collection_items()))
    first = item.child
    if not isinstance(first, Topic):
        raise click.ClickException(f"{course.slug} item 1 is not a topic.")
    if not TopicProgress._base_manager.filter(
        course_progress=record, collection_item=item, complete_time__isnull=False
    ).exists():
        TopicProgress._base_manager.update_or_create(
            course_progress=record,
            collection_item=item,
            defaults={"site": site, "topic": first, "complete_time": timezone.now()},
        )
    click.echo(f"[3] {course.slug}: item 1 '{first.title}' completed")


def _ensure_solo_org(site: Site, user: User) -> Organisation:
    org = _ensure_organisation(site, SOLO_ORG_NAME, SOLO_ORG_SLUG)
    # Anyone else on its staff would break "only staff member".
    others = StaffMember._base_manager.filter(organisation=org).exclude(user=user)
    if others.exists():
        click.echo(f"[4] Removed other StaffMember rows: {others.delete()}")
    other_roles = ObjectRoleAssignment._base_manager.filter(
        object_id=str(org.pk)
    ).exclude(user=user)
    if other_roles.exists():
        click.echo(f"[4] Removed other role rows: {other_roles.delete()}")
    member = ensure_staff_member(user, org)
    if not member.is_active:
        member.is_active = True
        member.save(update_fields=["is_active"])
    assign_object_role(user, org, "organisation_admin", assigned_by=user)
    click.echo(
        f"[4] {org.name} ({org.slug}) pk {org.pk}: {user.email} sole staff/admin"
    )
    return org


def _ensure_delete_cohorts(site: Site, org: Organisation) -> None:
    cascade = _ensure_cohort(site, org, CASCADE_COHORT)
    blocked = _ensure_cohort(site, org, BLOCKED_COHORT)
    for cohort in (cascade, blocked):
        cleared = (
            CohortMembership._base_manager.filter(cohort=cohort).delete(),
            cohort.course_registrations.all().delete(),
        )
        click.echo(f"[5] {cohort.name} pk {cohort.pk} emptied: {cleared}")
    CohortDeadlineConfig._base_manager.get_or_create(
        cohort=cascade, defaults={"site": site}
    )
    CohortMessagingConfig._base_manager.get_or_create(
        cohort=cascade, defaults={"site": site}
    )


def _ensure_move_learner(site: Site) -> User:
    user = User._base_manager.filter(site=site, email=MOVE_LEARNER_EMAIL).first()
    if user is None:
        user = cast(
            User,
            UserFactory(
                site=site,
                email=MOVE_LEARNER_EMAIL,
                first_name="Morgan",
                last_name="Mover",
            ),
        )
        user.set_password(MOVE_LEARNER_PASSWORD)
        user.save(update_fields=["password"])
    EmailAddress.objects.update_or_create(
        user=user,
        email=MOVE_LEARNER_EMAIL,
        defaults={"verified": True, "primary": True},
    )
    return user


def _ensure_move_cohorts(site: Site, org: Organisation) -> None:
    source = _ensure_cohort(site, org, MOVE_SOURCE)
    destination = _ensure_cohort(site, org, MOVE_DESTINATION)
    learner = _learner(_ensure_move_learner(site), org, site)
    stray = CohortMembership._base_manager.filter(learner=learner).exclude(
        cohort=source
    )
    if stray.exists():
        click.echo(f"[6] Removed move learner's other memberships: {stray.delete()}")
    if not CohortMembership._base_manager.filter(
        learner=learner, cohort=source
    ).exists():
        CohortMembershipFactory(site=site, cohort=source, learner=learner)
    click.echo(
        f"[6] {MOVE_SOURCE} pk {source.pk} holds learner pk {learner.pk} "
        f"({MOVE_LEARNER_EMAIL}); {MOVE_DESTINATION} pk {destination.pk}"
    )


@click.command()
@click.option("--site-name", default="DemoDev", help="Site the data belongs to.")
def command(site_name: str) -> None:
    """Seed the admonition QA scenarios on SITE_NAME."""
    site = Site.objects.filter(name=site_name).first()
    if site is None:
        raise click.ClickException(f"No site named {site_name}.")
    _pin_current_site(site)
    user = User._base_manager.filter(email=QA_LOGIN).first()
    if user is None:
        raise click.ClickException(f"{QA_LOGIN} not found; run create_demo_data.")
    with _site_context(site):
        org = get_default_organisation(site)
        _ensure_widgets_toc(site)

        learner = _learner(user, org, site)
        _, paused_record = _registration_and_record(
            learner, _course(site, PAUSED_SLUG), site
        )
        _ensure_paused(paused_record, user)
        ended_registration, ended_record = _registration_and_record(
            learner, _course(site, ENDED_SLUG), site
        )
        _ensure_ended(ended_registration, ended_record, site)
        quiz = _course(site, QUIZ_SLUG)
        _, quiz_record = _registration_and_record(learner, quiz, site)
        _ensure_quiz_ready(quiz_record, quiz, site)

        _ensure_solo_org(site, user)
        _ensure_delete_cohorts(site, org)
        _ensure_move_cohorts(site, org)
    click.echo(f"Done. {QA_LOGIN}'s password was not changed.")
