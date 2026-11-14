"""Seed the site's default organisation with a small, named educator-QA baseline.

Run ``create_demo_data --yes`` and ``content_save demo_content <site>`` first.
On the site's default organisation (``demodev`` on DemoDev) this builds,
idempotently:

* demodev@email.com: site_admin, organisation_admin and a StaffMember row.
* "QA cohort A" (active): Alice, Aaron, Amy and the pending Penny, registered on
  two demo courses with several topics.
* "QA cohort B" (active): Quinn and Bea, registered on one demo course.
* "QA cohort inactive" (inactive): the deactivated Dan.
* "QA cohort empty" (active): no learners, no registrations.
* Quinn: an active individual registration on the quiz demo course with a
  completed quiz attempt, plus an inactive individual registration.
* Penny: a pending account (unusable password, never logged in).
* Cora: a staff member whose only role is cohort_admin on QA cohort A.
* Audit log entries 30 and 10 days old, and fresh ones from the real services.
* A conversation between Alice and Cora.

Every login-ready persona's password is ``testpass123`` with a verified primary
EmailAddress.

Usage:
    uv run python manage.py qa_create_dev_org_baseline
    uv run python manage.py qa_create_dev_org_baseline --site-name DemoDev
"""

from __future__ import annotations

from datetime import timedelta
from typing import cast

import djclick as click
from allauth.account.models import EmailAddress

from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.utils import timezone

from freedom_ls.accounts.account_setup import match_or_create_user
from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.audit_log.factories import AuditLogEntryFactory
from freedom_ls.audit_log.models import AuditLogEntry
from freedom_ls.audit_log.writer import subject_key
from freedom_ls.comms.models import Conversation
from freedom_ls.content_engine.models import ContentCollectionItem, Course
from freedom_ls.form_engine.models import Form
from freedom_ls.learner_management.factories import LearnerCourseRegistrationFactory
from freedom_ls.learner_management.learner_actions import (
    add_to_cohort,
    deactivate_learner,
)
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    CohortMembership,
    Learner,
    LearnerCourseRegistration,
)
from freedom_ls.learner_management.utils import ensure_learner, ensure_staff_member
from freedom_ls.learner_progress.factories import (
    CourseFormAttemptFactory,
    CourseProgressFactory,
)
from freedom_ls.learner_progress.models import CourseFormAttempt, CourseProgress
from freedom_ls.organisations.models import Organisation
from freedom_ls.organisations.utils import get_default_organisation
from freedom_ls.qa_helpers.management.commands.qa_create_cohort_administration_scenario import (
    _ensure_cohort,
    _ensure_cohort_registration,
)
from freedom_ls.qa_helpers.management.commands.qa_create_direct_messaging_scenario import (
    _Msg,
    _pair,
)
from freedom_ls.qa_helpers.management.commands.qa_create_organisation_scenarios import (
    _pin_current_site,
    _site_context,
)
from freedom_ls.role_based_permissions.utils import assign_object_role, assign_site_role

PASSWORD = "testpass123"  # noqa: S105  # pragma: allowlist secret  # dev-only QA credential
ADMIN_EMAIL = "demodev@email.com"
TOPICS_COURSE = "functionality-demo-show-end-with-topic"
SECOND_COURSE = "standard-markdown-demo-finance"
COHORT_B_COURSE = "functionality-demo-course-parts"
QUIZ_COURSE = "functionality-demo-show-end-with-quiz"
OLD_ENTRY_DAYS = (30, 10)


def _course(site: Site, slug: str) -> Course:
    course: Course | None = Course._base_manager.filter(site=site, slug=slug).first()
    if course is None:
        raise click.ClickException(
            f"Course {slug!r} not found on {site.name}; run "
            f"`content_save demo_content {site.name}` first."
        )
    return course


def _user(site: Site, email: str, first: str, last: str) -> User:
    """A login-ready user: password PASSWORD, verified primary EmailAddress."""
    user: User | None = User._base_manager.filter(email=email).first()
    if user is None:
        user = cast(
            User,
            UserFactory(
                site=site,
                email=email,
                first_name=first,
                last_name=last,
                password=PASSWORD,
            ),
        )
    else:
        user.is_active = True
        user.set_password(PASSWORD)
        user.save(update_fields=["is_active", "password"])
    EmailAddress.objects.update_or_create(
        user=user, email=email, defaults={"verified": True, "primary": True}
    )
    return user


def _join(learner: Learner, cohort: Cohort, actor: User) -> None:
    if not CohortMembership._base_manager.filter(
        cohort=cohort, learner=learner
    ).exists():
        add_to_cohort(learner, cohort, actor=actor)


def _individual_registration(
    site: Site, learner: Learner, course: Course, is_active: bool
) -> LearnerCourseRegistration:
    reg: LearnerCourseRegistration | None = (
        LearnerCourseRegistration._base_manager.filter(
            learner=learner, course=course
        ).first()
    )
    if reg is None:
        reg = cast(
            LearnerCourseRegistration,
            LearnerCourseRegistrationFactory(
                site=site, learner=learner, course=course, is_active=is_active
            ),
        )
    elif reg.is_active != is_active:
        reg.is_active = is_active
        reg.save(update_fields=["is_active"])
    return reg


def _quiz_attempt(
    site: Site, reg: LearnerCourseRegistration, course: Course
) -> CourseFormAttempt:
    placement = (
        ContentCollectionItem._base_manager.filter(
            collection_id=course.pk,
            child_type=ContentType.objects.get_for_model(Form),
        )
        .order_by("order")
        .first()
    )
    if placement is None:
        raise click.ClickException(f"{course.slug!r} places no form.")
    form = cast(Form, placement.child)
    record: CourseProgress | None = CourseProgress._base_manager.filter(
        learner_registration=reg
    ).first()
    if record is None:
        record = cast(
            CourseProgress,
            CourseProgressFactory(
                site=site,
                learner=reg.learner,
                course=course,
                learner_registration=reg,
                cohort_registration=None,
            ),
        )
    existing: CourseFormAttempt | None = CourseFormAttempt._base_manager.filter(
        course_progress=record, form_progress__form=form
    ).first()
    if existing is not None:
        return existing
    attempt = cast(
        CourseFormAttempt,
        CourseFormAttemptFactory(
            course_progress=record,
            form=form,
            collection_item=placement,
            site=site,
            form_progress__site=site,
        ),
    )
    attempt.form_progress.complete()
    return attempt


def _old_entries(
    site: Site, org: Organisation, actor: User, cohorts: list[Cohort]
) -> list[AuditLogEntry]:
    """cohort.created entries backdated past the 7-day window, once per cohort."""
    now = timezone.now()
    cohort_type = ContentType.objects.get_for_model(Cohort)
    entries: list[AuditLogEntry] = []
    for cohort, days in zip(cohorts, OLD_ENTRY_DAYS, strict=True):
        found: AuditLogEntry | None = AuditLogEntry.unscoped.filter(
            target_content_type=cohort_type,
            target_object_id=str(cohort.pk),
            action="cohort.created",
            created_at__lt=now - timedelta(days=7),
        ).first()
        if found is None:
            found = cast(
                AuditLogEntry,
                AuditLogEntryFactory(
                    site=site,
                    target=cohort,
                    organisation=org,
                    actor=actor,
                    actor_label=actor.display_name,
                    action="cohort.created",
                    subjects=[subject_key(cohort)],
                    created_at=now - timedelta(days=days),
                ),
            )
        entries.append(found)
    return entries


def _seed(site: Site) -> None:
    org = get_default_organisation(site)
    admin = User._base_manager.get(email=ADMIN_EMAIL)
    assign_site_role(admin, "site_admin", assigned_by=admin, site=site)
    assign_object_role(admin, org, "organisation_admin", assigned_by=admin)
    ensure_staff_member(admin, org)

    topics_course = _course(site, TOPICS_COURSE)
    second_course = _course(site, SECOND_COURSE)
    b_course = _course(site, COHORT_B_COURSE)
    quiz_course = _course(site, QUIZ_COURSE)

    cohort_a = _ensure_cohort(site, org, "QA cohort A")
    cohort_b = _ensure_cohort(site, org, "QA cohort B")
    # Built active: the membership service refuses an inactive cohort, so Dan
    # joins first and the cohort is switched off afterwards.
    cohort_off = _ensure_cohort(site, org, "QA cohort inactive")
    cohort_empty = _ensure_cohort(site, org, "QA cohort empty")
    _ensure_cohort_registration(site, cohort_a, topics_course)
    _ensure_cohort_registration(site, cohort_a, second_course)
    _ensure_cohort_registration(site, cohort_b, b_course)
    _ensure_cohort_registration(site, cohort_off, topics_course)

    def learner(email: str, first: str, last: str) -> Learner:
        return ensure_learner(_user(site, email, first, last), org)

    alice = learner("qa.alice@email.com", "Alice", "Adeyemi")
    aaron = learner("qa.aaron@email.com", "Aaron", "Abrahams")
    amy = learner("qa.amy@email.com", "Amy", "Achterberg")
    pending_user, _ = match_or_create_user(
        site, "qa.penny@email.com", "Penny", "Pending"
    )
    penny = ensure_learner(pending_user, org)
    quinn = learner("qa.quinn@email.com", "Quinn", "Quiz")
    bea = learner("qa.bea@email.com", "Bea", "Botha")
    # ensure_learner reactivates an existing row, so a re-run reuses Dan's
    # deactivated row rather than writing a second deactivation entry.
    dan_user = _user(site, "qa.dan@email.com", "Dan", "Deactivated")
    dan = Learner._base_manager.filter(
        user=dan_user, organisation=org
    ).first() or ensure_learner(dan_user, org)

    for member in (alice, aaron, amy, penny):
        _join(member, cohort_a, admin)
    for member in (quinn, bea):
        _join(member, cohort_b, admin)
    _join(dan, cohort_off, admin)
    cohort_off = _ensure_cohort(site, org, "QA cohort inactive", is_active=False)
    if Learner._base_manager.get(pk=dan.pk).is_active:
        deactivate_learner(dan, actor=admin, reason="QA baseline: left the programme")

    quiz_reg = _individual_registration(site, quinn, quiz_course, is_active=True)
    _individual_registration(site, quinn, second_course, is_active=False)
    attempt = _quiz_attempt(site, quiz_reg, quiz_course)

    cora = _user(site, "qa.cora@email.com", "Cora", "Cohortadmin")
    assign_object_role(cora, cohort_a, "cohort_admin", assigned_by=admin)
    ensure_staff_member(cora, org)

    old = _old_entries(site, org, admin, [cohort_a, cohort_b])

    users = {u.email: u for u in (alice.user, cora)}
    conversation = _pair(
        site,
        users,
        "qa-baseline-alice-cora",
        "qa.cora@email.com",
        "qa.alice@email.com",
        [
            _Msg("qa.cora@email.com", timedelta(days=1), "Welcome to QA cohort A!"),
            _Msg("qa.alice@email.com", timedelta(hours=3), "Thanks, glad to be here."),
        ],
        {"qa.cora@email.com": 1, "qa.alice@email.com": 1},
        timezone.now(),
    )

    _report(
        site,
        org,
        [cohort_a, cohort_b, cohort_off, cohort_empty],
        attempt,
        old,
        conversation,
    )


def _report(
    site: Site,
    org: Organisation,
    cohorts: list[Cohort],
    attempt: CourseFormAttempt,
    old: list[AuditLogEntry],
    conversation: Conversation,
) -> None:
    click.secho("--- Dev organisation QA baseline ---", fg="cyan", bold=True)
    click.echo(f"SITE {site.name} ({site.domain}) ORG {org.name!r} slug={org.slug}")
    for cohort in cohorts:
        cohort.refresh_from_db()
        members = CohortMembership._base_manager.filter(cohort=cohort)
        regs = CohortCourseRegistration._base_manager.filter(cohort=cohort)
        click.echo(
            f"COHORT {cohort.name!r} pk={cohort.pk} active={cohort.is_active} "
            f"members={sorted(members.values_list('learner__user__email', flat=True))} "
            f"courses={sorted(regs.values_list('course__slug', flat=True))}"
        )
    for lrn in (
        Learner._base_manager.filter(organisation=org, user__email__startswith="qa.")
        .select_related("user")
        .order_by("user__email")
    ):
        user = lrn.user
        click.echo(
            f"LEARNER {user.email} user_pk={user.pk} learner_pk={lrn.pk} "
            f"active={lrn.is_active} usable_password={user.has_usable_password()} "
            f"regs={list(LearnerCourseRegistration._base_manager.filter(learner=lrn).values_list('course__slug', 'is_active'))}"
        )
    click.echo(
        f"QUIZ ATTEMPT pk={attempt.pk} form={attempt.form_progress.form.slug} "
        f"completed={attempt.form_progress.completed_time}"
    )
    for entry in old:
        click.echo(f"OLD AUDIT pk={entry.pk} {entry} at={entry.created_at:%Y-%m-%d}")
    week_ago = timezone.now() - timedelta(days=7)
    entries = AuditLogEntry.unscoped.filter(organisation=org)
    click.echo(
        f"AUDIT {org.slug}: older_than_7d={entries.filter(created_at__lt=week_ago).count()} "
        f"newer={entries.filter(created_at__gte=week_ago).count()}"
    )
    click.echo(
        f"ACTIVE LEARNERS in {org.slug}: "
        f"{Learner._base_manager.filter(organisation=org, is_active=True).count()}"
    )
    click.echo(f"CONVERSATION pk={conversation.pk} qa.cora <-> qa.alice")


@click.command()
@click.option("--site-name", default="DemoDev", help="Site to seed (default: DemoDev).")
def command(site_name: str) -> None:
    site = Site.objects.filter(name=site_name).first()
    if site is None:
        raise click.ClickException(f"Site {site_name!r} not found.")
    _pin_current_site(site)
    with _site_context(site):
        _seed(site)
