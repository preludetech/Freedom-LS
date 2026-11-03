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

Usage:
    uv run python manage.py qa_create_educator_polish_scenario
    uv run python manage.py qa_create_educator_polish_scenario --site-name DemoDev
"""

from __future__ import annotations

from typing import cast

import djclick as click
from allauth.account.models import EmailAddress

from django.contrib.sites.models import Site

from freedom_ls.accounts.account_setup import match_or_create_user
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import Course
from freedom_ls.form_engine.models import Form, FormStrategy, QuestionAnswer
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    CohortMembership,
)
from freedom_ls.organisations.models import Organisation
from freedom_ls.qa_helpers.management.commands.qa_create_cohort_administration_scenario import (
    _ensure_cohort_registration,
    _ensure_member,
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


def _checkpoint_course(site: Site, key: str) -> Course:
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
    ).update(title=CHECKPOINT_TITLE)
    return course


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

        courses = [_checkpoint_course(site, key) for key in CHECKPOINT_COURSE_KEYS]
        checkpoint = build_report_cohort(
            site=site,
            cohort_name=CHECKPOINT_COHORT,
            num_learners=3,
            course_slugs=tuple(c.slug for c in courses),
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
    for course in courses:
        wrong = (
            QuestionAnswer.objects.filter(
                form_progress__form__title=CHECKPOINT_TITLE,
                form_progress__course_attempt__course_progress__course=course,
                form_progress__completed_time__isnull=False,
            )
            .exclude(selected_options__correct=True)
            .count()
        )
        click.echo(f"COURSE {course.title!r} slug={course.slug} wrong_answers={wrong}")
    click.echo(f"NAMELESS LEARNER {nameless.email} pk={nameless.pk}")
    click.echo(f"NAMELESS EDUCATOR {educator.email!r} (password = that email)")
