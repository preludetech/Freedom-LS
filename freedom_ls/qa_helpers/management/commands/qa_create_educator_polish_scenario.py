"""Top up the educator-interface QA seeds for the docs-and-polish frontend QA pass.

Run AFTER qa_create_educator_interface_seed and the cohort, learner, bulk and
member administration scenarios (the bulk scenario's reset strips some of what
this adds, so re-run this after it). On the target site it makes, idempotently:

* demodev@email.com ``organisation_admin`` of Northside (main) and Southside
  (second org, so the switcher shows). Eastside is left untouched: no members,
  no audit-log entries.
* Cohort Old (inactive) registered on Course Pub again.
* Two courses, each holding one quiz titled "Checkpoint", both registered to
  "QA Checkpoint Cohort" (Northside) whose learners carry scored attempts with
  wrong answers.
* A nameless learner (no first/last name) in the Checkpoint cohort.
* "QA Over Limit Cohort" (Northside) with more learners than a lowered
  REPORTS_MAX_LEARNERS (set it to 5 in config/settings_local.py).
* A nameless educator with a mixed-case email, cohort_viewer on the Checkpoint
  cohort. Password: the email as stored.
* A second nameless educator whose stored email is all lower case, also
  cohort_viewer on the Checkpoint cohort. Password: the email.
* A third course whose only quiz has a unique title ("Recap Quiz"), also
  registered to the Checkpoint cohort, with wrong answers recorded.
* Quietside: an organisation where cohort.viewer@qa.test is cohort_viewer on an
  empty cohort, with no learners and no audit-log entries (the grant's own
  entry is deleted).

Usage:
    uv run python manage.py qa_create_educator_polish_scenario
    uv run python manage.py qa_create_educator_polish_scenario --site-name DemoDev
"""

from __future__ import annotations

from datetime import timedelta
from typing import cast

import djclick as click
from allauth.account.models import EmailAddress

from django.contrib.sites.models import Site
from django.utils import timezone

from freedom_ls.accounts.account_setup import match_or_create_user
from freedom_ls.accounts.models import User
from freedom_ls.audit_log.models import AuditLogEntry
from freedom_ls.content_engine.models import Course
from freedom_ls.form_engine.models import Form, FormStrategy, QuestionAnswer
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    CohortMembership,
    OrganisationMember,
)
from freedom_ls.organisations.models import Organisation
from freedom_ls.qa_helpers.management.commands.qa_create_cohort_administration_scenario import (
    _ensure_cohort,
    _ensure_cohort_registration,
    _ensure_member,
    _ensure_organisation,
)
from freedom_ls.qa_helpers.management.commands.qa_create_organisation_scenarios import (
    _pin_current_site,
    _site_context,
)
from freedom_ls.qa_helpers.management.commands.qa_create_report_cohort import (
    build_report_cohort,
)
from freedom_ls.qa_helpers.management.commands.qa_create_report_course import (
    build_report_course,
)
from freedom_ls.role_based_permissions.utils import assign_object_role

SUPERUSER_EMAIL = "demodev@email.com"
MAIN_ORG_SLUG = "northside"
SECOND_ORG_SLUG = "southside"
CHECKPOINT_COURSE_KEYS = ("checkpoint-a", "checkpoint-b")
CHECKPOINT_TITLE = "Checkpoint"
CHECKPOINT_COHORT = "QA Checkpoint Cohort"
OVER_LIMIT_COHORT = "QA Over Limit Cohort"
OVER_LIMIT_LEARNERS = 7
NAMELESS_LEARNER_EMAIL = "qa-nameless-learner@email.com"
NAMELESS_EDUCATOR_EMAIL = "Nameless.Educator@Example.com"
NAMELESS_LOWER_EDUCATOR_EMAIL = "nameless.lower.educator@example.com"
RECAP_COURSE_KEY = "recap-c"
RECAP_TITLE = "Recap Quiz"
QUIET_ORG_NAME = "Quietside"
QUIET_ORG_SLUG = "quietside"
QUIET_COHORT = "Cohort Q"
COHORT_VIEWER_EMAIL = "cohort.viewer@qa.test"


def _org(site: Site, slug: str) -> Organisation:
    return cast(Organisation, Organisation._base_manager.get(site=site, slug=slug))


def _ready_user(site: Site, email: str) -> User:
    """A login-ready user with no name; password is the email as stored."""
    user, _ = match_or_create_user(site, email)
    user.first_name = ""
    user.last_name = ""
    user.is_active = True
    user.set_password(user.email)
    user.save(update_fields=["first_name", "last_name", "is_active", "password"])
    EmailAddress.objects.update_or_create(
        user=user, email=user.email, defaults={"verified": True, "primary": True}
    )
    return user


def _quiz_course(site: Site, key: str, title: str) -> Course:
    course = build_report_course(
        site=site,
        course_key=key,
        num_items=3,
        num_quizzes=1,
        questions_per_quiz=3,
        big_quiz_questions=0,
        pass_percentage=50,
        no_pass_mark_quiz=False,
    )
    Form.objects.filter(
        slug=f"qa-report-{key}-quiz-01", site=site, strategy=FormStrategy.QUIZ
    ).update(title=title)
    return course


def _quiet_organisation(site: Site) -> Organisation:
    """An org whose only member is the cohort viewer, with no audit entries."""
    org = _ensure_organisation(site, QUIET_ORG_NAME, QUIET_ORG_SLUG)
    cohort = _ensure_cohort(site, org, QUIET_COHORT)
    viewer = User.objects.get(email=COHORT_VIEWER_EMAIL)
    OrganisationMember._base_manager.update_or_create(
        site=site, user=viewer, organisation=org, defaults={"is_active": True}
    )
    assign_object_role(viewer, cohort, "cohort_viewer")
    # The grant writes its own entry; prune_before is the log's one delete path.
    entries = AuditLogEntry.objects.filter(organisation=org)
    for entry in entries:
        click.secho(f"Pruning audit entry pk={entry.pk} {entry}", fg="yellow")
    if entries.exists():
        pruned = entries.prune_before(timezone.now() + timedelta(seconds=1))
        click.secho(f"Pruned {pruned} audit entries on {org.slug}", fg="yellow")
    return org


@click.command()
@click.option("--site-name", default="DemoDev", help="Site name (default: DemoDev)")
def command(site_name: str) -> None:
    """Top up the educator QA seeds for the docs-and-polish pass."""
    site = Site.objects.get(name=site_name)
    _pin_current_site(site)
    with _site_context(site):
        north = _org(site, MAIN_ORG_SLUG)
        south = _org(site, SECOND_ORG_SLUG)
        superuser = User.objects.get(email=SUPERUSER_EMAIL)
        for org in (north, south):
            assign_object_role(superuser, org, "organisation_admin")

        course_pub = Course.objects.get(slug="course-pub", site=site)
        cohort_old = Cohort._base_manager.get(organisation=north, name="Cohort Old")
        _ensure_cohort_registration(site, cohort_old, course_pub)

        courses = [
            _quiz_course(site, key, CHECKPOINT_TITLE) for key in CHECKPOINT_COURSE_KEYS
        ]
        recap = _quiz_course(site, RECAP_COURSE_KEY, RECAP_TITLE)
        checkpoint = build_report_cohort(
            site=site,
            cohort_name=CHECKPOINT_COHORT,
            num_learners=3,
            course_slugs=tuple(c.slug for c in [*courses, recap]),
            inactive_course_slugs=(),
            num_flagged=1,
            no_progress=False,
            email_prefix="qa-checkpoint-learner",
            educator_email=None,
            organisation=north,
        )
        nameless = _ready_user(site, NAMELESS_LEARNER_EMAIL)
        _ensure_member(site, checkpoint, nameless)

        educator = _ready_user(site, NAMELESS_EDUCATOR_EMAIL)
        assign_object_role(educator, checkpoint, "cohort_viewer")
        lower_educator = _ready_user(site, NAMELESS_LOWER_EDUCATOR_EMAIL)
        assign_object_role(lower_educator, checkpoint, "cohort_viewer")
        quiet = _quiet_organisation(site)

        over = build_report_cohort(
            site=site,
            cohort_name=OVER_LIMIT_COHORT,
            num_learners=OVER_LIMIT_LEARNERS,
            course_slugs=(course_pub.slug,),
            inactive_course_slugs=(),
            num_flagged=0,
            no_progress=True,
            email_prefix="qa-overlimit-learner",
            educator_email=None,
            organisation=north,
        )

    click.secho("--- Educator polish QA data ---", fg="cyan", bold=True)
    for cohort in (cohort_old, checkpoint, over):
        regs = list(
            CohortCourseRegistration._base_manager.filter(cohort=cohort).values_list(
                "course__title", flat=True
            )
        )
        members = CohortMembership._base_manager.filter(cohort=cohort).count()
        click.echo(
            f"COHORT {cohort.name!r} pk={cohort.pk} active={cohort.is_active} "
            f"members={members} courses={regs}"
        )
    for course, title in [
        *((c, CHECKPOINT_TITLE) for c in courses),
        (recap, RECAP_TITLE),
    ]:
        wrong = (
            QuestionAnswer.objects.filter(
                form_progress__form__title=title,
                form_progress__course_attempt__course_progress__course=course,
                form_progress__completed_time__isnull=False,
            )
            .exclude(selected_options__correct=True)
            .count()
        )
        click.echo(f"COURSE {course.title!r} slug={course.slug} wrong_answers={wrong}")
    click.echo(f"NAMELESS LEARNER {nameless.email} pk={nameless.pk}")
    click.echo(f"NAMELESS EDUCATOR {educator.email!r} (password = that email)")
    click.echo(
        f"NAMELESS LOWER EDUCATOR {lower_educator.email!r} (password = that email)"
    )
    click.echo(
        f"QUIET ORG {quiet.name!r} slug={quiet.slug} "
        f"audit_entries={AuditLogEntry._base_manager.filter(organisation=quiet).count()}"
    )
