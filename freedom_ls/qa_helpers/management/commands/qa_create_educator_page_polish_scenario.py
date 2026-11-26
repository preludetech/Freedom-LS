"""Seed the browser-QA data for the educator-interface page polish pass.

Needs the standard dev baseline first::

    uv run python manage.py create_demo_data --yes
    uv run python manage.py content_save ./demo_content DemoDev

Then (idempotent)::

    uv run python manage.py qa_create_educator_page_polish_scenario
    uv run python manage.py qa_create_bulk_learners --active --count 210 \
        --prefix qa.polish.bulk --name "Polish Bulk"

On the site's default organisation it makes:

* demodev@email.com: site_admin, organisation_admin and a StaffMember row.
* Five standalone QA courses (four topics and one pass-marked quiz each). The
  "Shared" course is owned by Harbour College and shared with the default
  organisation, so it carries a "Shared by" line. One title runs past 60
  characters.
* "QA Polish Cohort", registered on the Flagged course, holding learners A, D,
  E (no recorded activity) and F (last activity 20 days ago).
* Learner A (40+ character email) on all five courses: Flagged through the
  cohort with a failed latest quiz six days ago; Shared in progress an hour
  ago; Complete at 100%; Not Started individually with NO course progress
  record (the registration is bulk-inserted so no signal mints one); the long
  title in progress five days ago.
* Learner B on exactly three courses, learner C on none.
* Learner D on the Flagged course through the cohort (failed latest quiz) and
  individually (one topic, no quiz).
* A cohort_viewer educator on QA Polish Cohort only: sees its learners, cannot
  rename them.

Activity times are relative to the first run; a re-run leaves existing progress
alone. Every persona's password is ``testpass123``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import cast

import djclick as click

from django.contrib.sites.models import Site
from django.utils import timezone

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import ContentCollectionItem, Course, Topic
from freedom_ls.form_engine.models import Form, FormStrategy
from freedom_ls.learner_management.learner_actions import add_to_cohort
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    Learner,
    LearnerCourseRegistration,
)
from freedom_ls.learner_management.utils import ensure_learner, ensure_staff_member
from freedom_ls.learner_progress.models import CourseProgress, TopicProgress
from freedom_ls.learner_progress.utils import ensure_course_progress_record
from freedom_ls.organisations.models import Organisation
from freedom_ls.organisations.utils import get_default_organisation
from freedom_ls.qa_helpers.management.commands.qa_create_cohort_administration_scenario import (
    _ensure_cohort,
    _ensure_cohort_registration,
)
from freedom_ls.qa_helpers.management.commands.qa_create_dev_org_baseline import (
    PASSWORD,
    _individual_registration,
    _user,
)
from freedom_ls.qa_helpers.management.commands.qa_create_organisation_scenarios import (
    _pin_current_site,
    _site_context,
)
from freedom_ls.qa_helpers.management.commands.qa_create_report_cohort import (
    _complete_attempt,
    _has_existing_progress,
    _quiz_questions,
    _settle_record,
)
from freedom_ls.qa_helpers.management.commands.qa_create_report_course import (
    build_report_course,
)
from freedom_ls.qa_helpers.management.commands.qa_create_single_org_educator import (
    _drop_other_grants,
    _ensure_consents,
)
from freedom_ls.role_based_permissions.utils import assign_object_role, assign_site_role

ADMIN_EMAIL = "demodev@email.com"
SHARING_ORG_SLUG = "harbour-college"
COHORT_NAME = "QA Polish Cohort"
VIEWER_ROLE = "cohort_viewer"
NUM_ITEMS = 5
QUESTIONS_PER_QUIZ = 4
PASS_PERCENTAGE = 50

# course key -> title
COURSES = {
    "polish-flagged": "QA Polish Flagged Course",
    "polish-shared": "QA Polish Shared Course",
    "polish-complete": "QA Polish Complete Course",
    "polish-not-started": "QA Polish Not Started Course",
    "polish-long": (
        "QA Polish Course With A Deliberately Long Title To Check The Ellipsis"
    ),
}

LEARNER_A = (
    "alexandra.achterberg-longaddress@qa-polish.test",
    "Alexandra",
    "Achterberg",
)
LEARNER_B = ("qa.polish.bongani@qa-polish.test", "Bongani", "Botha")
LEARNER_C = ("qa.polish.chloe@qa-polish.test", "Chloe", "Cele")
LEARNER_D = ("qa.polish.dawit@qa-polish.test", "Dawit", "Desta")
LEARNER_E = ("qa.polish.eli@qa-polish.test", "Eli", "Engelbrecht")
LEARNER_F = ("qa.polish.fiona@qa-polish.test", "Fiona", "Fourie")
VIEWER = ("qa.polish.viewer@qa-polish.test", "Vusi", "Viewer")

QUIZ_PASSED = "passed"
QUIZ_FAILED = "failed"


@dataclass(frozen=True)
class Progress:
    """How far one course progress record gets: the first `topics` topics,
    then the quiz (passed, failed or untouched), all at `days_ago`."""

    topics: int
    quiz: str | None
    days_ago: float


def _items(course: Course) -> list[ContentCollectionItem]:
    return [
        ci
        for ci in course.viewable_collection_items()
        if isinstance(ci.child, Topic | Form)
    ]


def _apply_progress(
    site: Site, record: CourseProgress, course: Course, plan: Progress, now: datetime
) -> str:
    """Write the topic completions and quiz attempt `plan` asks for, once."""
    items = _items(course)
    if _has_existing_progress(record, items):
        return "kept existing progress"
    at = now - timedelta(days=plan.days_ago)
    topics = [ci for ci in items if isinstance(ci.child, Topic)][: plan.topics]
    for offset, ci in enumerate(topics):
        TopicProgress.objects.update_or_create(
            course_progress=record,
            collection_item=ci,
            defaults={
                "topic": ci.child,
                "complete_time": at - timedelta(minutes=10 * (len(topics) - offset)),
                "site": site,
            },
        )
    if plan.quiz is not None:
        quiz_item = next(
            ci
            for ci in items
            if isinstance(ci.child, Form) and ci.child.strategy == FormStrategy.QUIZ
        )
        questions, options = _quiz_questions(cast(Form, quiz_item.child))
        wrong = {q.order for q in questions} if plan.quiz == QUIZ_FAILED else set[int]()
        _complete_attempt(
            record=record,
            form=cast(Form, quiz_item.child),
            collection_item=quiz_item,
            site=site,
            questions=questions,
            options_by_question=options,
            wrong_orders=wrong,
            learner_index=0,
            started_at=at - timedelta(minutes=5),
            completed_at=at,
        )
    _settle_record(record)
    CourseProgress._base_manager.filter(pk=record.pk).update(
        started_at=at - timedelta(hours=1), last_accessed_time=at
    )
    return (
        f"{plan.topics} topics, quiz {plan.quiz or 'untouched'}, {plan.days_ago:g}d ago"
    )


def _individual(
    site: Site, learner: Learner, course: Course, plan: Progress | None, now: datetime
) -> str:
    reg = _individual_registration(site, learner, course, is_active=True)
    record = ensure_course_progress_record(learner, course, reg)
    return (
        "no progress"
        if plan is None
        else _apply_progress(site, record, course, plan, now)
    )


def _through_cohort(
    site: Site,
    learner: Learner,
    reg: CohortCourseRegistration,
    plan: Progress | None,
    now: datetime,
) -> str:
    record = ensure_course_progress_record(learner, reg.course, reg)
    return (
        "no progress"
        if plan is None
        else _apply_progress(site, record, reg.course, plan, now)
    )


def _registration_without_record(
    site: Site, learner: Learner, course: Course
) -> LearnerCourseRegistration:
    """An active individual registration with no course progress record.

    bulk_create skips post_save, which is the only place a record is minted.
    """
    reg = LearnerCourseRegistration._base_manager.filter(
        learner=learner, course=course
    ).first()
    if reg is None:
        reg = LearnerCourseRegistration._base_manager.bulk_create(
            [
                LearnerCourseRegistration(
                    site=site, learner=learner, course=course, is_active=True
                )
            ]
        )[0]
    if CourseProgress._base_manager.filter(learner_registration=reg).exists():
        click.secho(
            f"WARNING: {learner} already has a course progress record for "
            f"{course.title!r}; left in place.",
            fg="red",
        )
    return cast(LearnerCourseRegistration, reg)


def _courses(site: Site, org: Organisation) -> dict[str, Course]:
    courses: dict[str, Course] = {}
    for key, title in COURSES.items():
        course = build_report_course(
            site=site,
            course_key=key,
            num_items=NUM_ITEMS,
            num_quizzes=1,
            questions_per_quiz=QUESTIONS_PER_QUIZ,
            big_quiz_questions=0,
            pass_percentage=PASS_PERCENTAGE,
            no_pass_mark_quiz=False,
        )
        if course.title != title:
            Course._base_manager.filter(pk=course.pk).update(title=title)
            course.refresh_from_db()
        courses[key] = course
    sharer = Organisation._base_manager.get(site=site, slug=SHARING_ORG_SLUG)
    shared = courses["polish-shared"]
    shared.organisations.set([sharer])
    shared.shared_with.set([org])
    return courses


def _seed(site: Site) -> None:
    now = timezone.now()
    org = get_default_organisation(site)
    admin = User._base_manager.get(email=ADMIN_EMAIL)
    assign_site_role(admin, "site_admin", assigned_by=admin, site=site)
    assign_object_role(admin, org, "organisation_admin", assigned_by=admin)
    ensure_staff_member(admin, org)

    c = _courses(site, org)
    cohort = _ensure_cohort(site, org, COHORT_NAME)
    cohort_reg = _ensure_cohort_registration(site, cohort, c["polish-flagged"])

    def learner(spec: tuple[str, str, str]) -> Learner:
        return ensure_learner(_user(site, *spec), org)

    a, b, lc, d, e, f = (
        learner(spec)
        for spec in (LEARNER_A, LEARNER_B, LEARNER_C, LEARNER_D, LEARNER_E, LEARNER_F)
    )
    for member in (a, d, e, f):
        add_to_cohort(member, cohort, actor=admin)

    log: list[str] = []
    log.append(
        "A flagged (cohort): "
        + _through_cohort(site, a, cohort_reg, Progress(2, QUIZ_FAILED, 6), now)
    )
    log.append(
        "A shared: "
        + _individual(site, a, c["polish-shared"], Progress(2, None, 1 / 24), now)
    )
    log.append(
        "A complete: "
        + _individual(site, a, c["polish-complete"], Progress(4, QUIZ_PASSED, 3), now)
    )
    _registration_without_record(site, a, c["polish-not-started"])
    log.append("A not started: registration only, no record")
    log.append(
        "A long: " + _individual(site, a, c["polish-long"], Progress(1, None, 5), now)
    )
    log.append(
        "B shared: "
        + _individual(site, b, c["polish-shared"], Progress(1, None, 2), now)
    )
    log.append(
        "B complete: "
        + _individual(site, b, c["polish-complete"], Progress(4, QUIZ_PASSED, 1), now)
    )
    log.append(
        "B long: " + _individual(site, b, c["polish-long"], Progress(2, None, 3), now)
    )
    log.append(
        "D flagged (cohort): "
        + _through_cohort(site, d, cohort_reg, Progress(2, QUIZ_FAILED, 2), now)
    )
    log.append(
        "D flagged (individual): "
        + _individual(site, d, c["polish-flagged"], Progress(1, None, 1), now)
    )
    log.append("E (cohort): " + _through_cohort(site, e, cohort_reg, None, now))
    log.append(
        "F (cohort): "
        + _through_cohort(site, f, cohort_reg, Progress(1, None, 20), now)
    )

    viewer = _user(site, *VIEWER)
    _ensure_consents(site, viewer)
    dropped = _drop_other_grants(viewer, cohort, VIEWER_ROLE)
    assign_object_role(viewer, cohort, VIEWER_ROLE, assigned_by=admin)

    _report(site, org, cohort, c, [a, b, lc, d, e, f], viewer, log, dropped)


def _report(
    site: Site,
    org: Organisation,
    cohort: Cohort,
    courses: dict[str, Course],
    learners: list[Learner],
    viewer: User,
    log: list[str],
    dropped: list[str],
) -> None:
    base = f"/educator/organisations/{org.slug}"
    click.secho("--- Educator page polish QA data ---", fg="cyan", bold=True)
    click.echo(f"SITE {site.name} pk={site.pk} domain={site.domain}")
    click.echo(f"ORG {org.name!r} slug={org.slug} pk={org.pk}")
    click.echo(f"ADMIN {ADMIN_EMAIL} / {ADMIN_EMAIL}")
    for course in courses.values():
        sharers = list(course.organisations.values_list("name", flat=True))
        click.echo(
            f"COURSE {course.title!r} ({len(course.title)} chars) pk={course.pk} "
            f"slug={course.slug} owners={sharers} "
            f"shared_with={list(course.shared_with.values_list('slug', flat=True))} "
            f"url={base}/courses/{course.pk}"
        )
    click.echo(f"COHORT {cohort.name!r} pk={cohort.pk} url={base}/cohorts/{cohort.pk}")
    for line in log:
        click.echo(f"PROGRESS {line}")
    for learner in learners:
        regs = list(
            LearnerCourseRegistration._base_manager.filter(
                learner=learner, is_active=True
            ).values_list("course__title", flat=True)
        )
        records = list(
            CourseProgress._base_manager.filter(learner=learner).values_list(
                "course__title", "progress_percentage", "cohort_registration_id"
            )
        )
        click.echo(
            f"LEARNER {learner.user.display_name!r} email={learner.user.email} "
            f"({len(learner.user.email)} chars) pk={learner.pk} "
            f"password={PASSWORD} url={base}/learners/{learner.pk}"
        )
        click.echo(f"  individual registrations={regs}")
        click.echo(f"  progress records (title, stored %, via cohort reg)={records}")
    click.echo(
        f"VIEWER {viewer.email} / {PASSWORD} {VIEWER_ROLE} on {cohort.name!r}; "
        f"other grants deactivated: {dropped or 'none'}"
    )
    click.echo(f"LEARNERS LIST {base}/learners")


@click.command()
@click.option("--site-name", default="DemoDev", help="Site name (default: DemoDev)")
def command(site_name: str) -> None:
    """Seed the educator page polish QA scenario."""
    site = Site.objects.get(name=site_name)
    _pin_current_site(site)
    with _site_context(site):
        _seed(site)
