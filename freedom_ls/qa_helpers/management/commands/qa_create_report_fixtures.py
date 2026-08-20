"""Build the whole cohort-progress-report QA fixture matrix in one command.

The report's layout behaviour changes with two axes at once -- cohort size
lengthens the landscape summary table, course length widens it -- so the QA plan
(``spec_dd/2. in progress/basic_reports/3a. report_generation_qa/
frontend_qa_report_generation.md``) defines eleven fixtures
spanning 0 to 40 students and 1 to 12+ quizzes, plus the degenerate,
no-pass-mark and blank-answer cases. This command builds all of them, plus the
two users the permission checks need.

It is a thin orchestrator: the work is done by ``build_report_course`` and
``build_report_cohort``, imported from the two builder commands so the whole
matrix is built in one process rather than by shelling out per fixture.

Idempotent. Re-running rebuilds nothing that already exists.

Usage:
    uv run python manage.py qa_create_report_fixtures
    uv run python manage.py qa_create_report_fixtures --only xl-cohort-long-course
    uv run python manage.py qa_create_report_fixtures --long-course-quizzes 16
"""

import dataclasses

import djclick as click
from guardian.shortcuts import assign_perm

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site

from freedom_ls.accounts.models import User
from freedom_ls.qa_helpers.management.commands.qa_create_report_cohort import (
    _get_or_create_user,
    _get_site,
    build_report_cohort,
)
from freedom_ls.qa_helpers.management.commands.qa_create_report_course import (
    build_report_course,
)
from freedom_ls.reports.models import GeneratedReport
from freedom_ls.student_management.models import Cohort

EDUCATOR_EMAIL = "qa-report-educator@email.com"
RESTRICTED_EMAIL = "qa-report-restricted@email.com"

# The cohort the restricted staff user CAN see. Every other cohort is the
# "cohort B" of the permission checks.
PERMITTED_FIXTURE_KEY = "standard-cohort-medium-course"


@dataclasses.dataclass(frozen=True)
class CourseFixture:
    key: str
    num_items: int
    num_quizzes: int
    questions_per_quiz: int
    big_quiz_questions: int
    no_pass_mark_quiz: bool
    # Clears ``required`` on each quiz's last question, so a learner can leave
    # it blank. Defaulted, because only the blank-answer fixture wants it.
    optional_last_question: bool = False

    @property
    def slug(self) -> str:
        return f"qa-report-{self.key}-course"


@dataclasses.dataclass(frozen=True)
class CohortFixture:
    key: str
    cohort_name: str
    email_prefix: str
    num_students: int
    course_keys: tuple[str, ...]
    inactive_course_keys: tuple[str, ...]
    num_flagged: int
    no_progress: bool
    purpose: str


# `big_quiz_questions` on the medium and long courses is what makes the report's
# "showing worst 10 of N" confusion cap disclosure appear: the cap is 10
# questions per quiz, so one quiz has to carry more than 10 questions that
# somebody got wrong.
COURSE_FIXTURES: list[CourseFixture] = [
    CourseFixture(
        key="short",
        num_items=4,
        num_quizzes=1,
        questions_per_quiz=4,
        big_quiz_questions=0,
        no_pass_mark_quiz=False,
    ),
    CourseFixture(
        key="medium",
        num_items=12,
        num_quizzes=4,
        questions_per_quiz=4,
        big_quiz_questions=14,
        no_pass_mark_quiz=False,
    ),
    CourseFixture(
        key="long",
        num_items=30,
        num_quizzes=12,
        questions_per_quiz=5,
        big_quiz_questions=14,
        no_pass_mark_quiz=False,
    ),
    CourseFixture(
        key="nopass",
        num_items=12,
        num_quizzes=4,
        questions_per_quiz=4,
        big_quiz_questions=0,
        no_pass_mark_quiz=True,
    ),
    CourseFixture(
        key="second",
        num_items=8,
        num_quizzes=2,
        questions_per_quiz=4,
        big_quiz_questions=0,
        no_pass_mark_quiz=False,
    ),
    # Two quizzes and no topics at all, deliberately: the completion ladder
    # gives the lower rungs only the first slot or two of a course, so a course
    # that opens on a quiz is the only way most of the cohort reaches one. Every
    # student with any progress therefore sits quiz 1, whose last question is
    # optional and so is the one they can leave blank.
    CourseFixture(
        key="blank",
        num_items=2,
        num_quizzes=2,
        questions_per_quiz=4,
        big_quiz_questions=0,
        no_pass_mark_quiz=False,
        optional_last_question=True,
    ),
]

COHORT_FIXTURES: list[CohortFixture] = [
    CohortFixture(
        key="empty-cohort",
        cohort_name="QA Report Empty Cohort",
        email_prefix="qa-report-empty",
        num_students=0,
        course_keys=("short",),
        inactive_course_keys=(),
        num_flagged=0,
        no_progress=False,
        purpose="Zero students: the report must say so, not crash.",
    ),
    CohortFixture(
        key="no-registrations",
        cohort_name="QA Report No Registrations Cohort",
        email_prefix="qa-report-noreg",
        num_students=5,
        course_keys=(),
        inactive_course_keys=(),
        num_flagged=0,
        no_progress=True,
        purpose="Students but no course registrations: the report must state it.",
    ),
    CohortFixture(
        key="tiny-cohort-short-course",
        cohort_name="QA Report Tiny Cohort",
        email_prefix="qa-report-tiny",
        num_students=3,
        course_keys=("short",),
        inactive_course_keys=(),
        num_flagged=1,
        no_progress=False,
        purpose="Smallest real report; plain counts, no table split.",
    ),
    CohortFixture(
        key="small-cohort-medium-course",
        cohort_name="QA Report Small Cohort",
        email_prefix="qa-report-small",
        num_students=9,
        course_keys=("medium",),
        inactive_course_keys=(),
        num_flagged=3,
        no_progress=False,
        purpose="Under 10 students: confusions must show plain counts, no percentages.",
    ),
    CohortFixture(
        key="standard-cohort-medium-course",
        cohort_name="QA Report Standard Cohort",
        email_prefix="qa-report-std",
        num_students=9,
        course_keys=("medium",),
        inactive_course_keys=(),
        num_flagged=3,
        no_progress=False,
        purpose="The everyday case; the baseline read-through.",
    ),
    CohortFixture(
        key="large-cohort-medium-course",
        cohort_name="QA Report Large Cohort",
        email_prefix="qa-report-large",
        num_students=25,
        course_keys=("medium",),
        inactive_course_keys=(),
        num_flagged=6,
        no_progress=False,
        purpose="Multi-page tables, repeated header rows, percentages in confusions.",
    ),
    CohortFixture(
        key="xl-cohort-long-course",
        cohort_name="QA Report XL Cohort",
        email_prefix="qa-report-xl",
        num_students=40,
        course_keys=("long",),
        inactive_course_keys=(),
        num_flagged=18,
        no_progress=False,
        purpose="Both caps at once: attention list capped at 12, quiz columns past the budget.",
    ),
    CohortFixture(
        key="two-course-cohort",
        cohort_name="QA Report Two Course Cohort",
        email_prefix="qa-report-two",
        num_students=9,
        course_keys=("medium",),
        inactive_course_keys=("second",),
        num_flagged=2,
        no_progress=False,
        purpose="Both courses sectioned, the inactive registration marked inactive.",
    ),
    CohortFixture(
        key="no-progress-cohort",
        cohort_name="QA Report No Progress Cohort",
        email_prefix="qa-report-noprog",
        num_students=9,
        course_keys=("medium",),
        inactive_course_keys=(),
        num_flagged=0,
        no_progress=True,
        purpose="Every student takes the 'No activity recorded' branch.",
    ),
    CohortFixture(
        key="blank-answer-cohort",
        cohort_name="QA Report Blank Answer Cohort",
        email_prefix="qa-report-blank",
        num_students=9,
        course_keys=("blank",),
        inactive_course_keys=(),
        num_flagged=2,
        no_progress=False,
        purpose=(
            "Wrong answers with nothing selected: those rows must read "
            "'Not answered', not leave the 'Answers given' cell blank."
        ),
    ),
    CohortFixture(
        key="no-pass-mark-cohort",
        cohort_name="QA Report No Pass Mark Cohort",
        email_prefix="qa-report-nopass",
        num_students=9,
        course_keys=("nopass",),
        inactive_course_keys=(),
        num_flagged=2,
        no_progress=False,
        purpose="A quiz with quiz_pass_percentage unset: score, no verdict, no crash.",
    ),
]

COURSES_BY_KEY = {fixture.key: fixture for fixture in COURSE_FIXTURES}
COHORTS_BY_KEY = {fixture.key: fixture for fixture in COHORT_FIXTURES}


def _reset_fixtures(site: Site, fixtures: list[CohortFixture]) -> tuple[int, int]:
    """Delete the given fixture cohorts and their students, cascading progress.

    Scoped to QA-owned rows only: cohorts are matched by their fixture name and
    students by their fixture email prefix, so nothing a human created by hand
    is touched. The QA report courses are left in place -- they are rebuilt
    idempotently and hold no per-student state.
    """
    deleted_students = 0
    for fixture in fixtures:
        students = User.objects.filter(
            email__startswith=f"{fixture.email_prefix}-", site=site
        )
        deleted_students += students.count()
        students.delete()
    deleted_cohorts, _ = Cohort.objects.filter(
        name__in=[fixture.cohort_name for fixture in fixtures], site=site
    ).delete()
    return deleted_cohorts, deleted_students


def _grant_report_admin_access(user: User) -> None:
    """Staff access plus every model permission on GeneratedReport.

    Model-level ``student_management.view_cohort`` is deliberately NOT granted:
    guardian's object-level lookups return everything to a user holding the
    global permission, which would defeat the point of a cohort-scoped user.
    """
    if not user.is_staff:
        user.is_staff = True
        user.save(update_fields=["is_staff"])
    content_type = ContentType.objects.get_for_model(GeneratedReport)
    user.user_permissions.add(*Permission.objects.filter(content_type=content_type))


@click.command()
@click.option(
    "--site-name",
    default="DemoDev",
    help="Site name to create the data on (default: 'DemoDev').",
)
@click.option(
    "--only",
    multiple=True,
    help="Fixture key(s) to build instead of the whole matrix. Repeatable.",
)
@click.option(
    "--long-course-quizzes",
    default=12,
    type=int,
    help=(
        "Quizzes on the long course (default: 12). Raise it until the landscape "
        "summary table splits, then record the number that did."
    ),
)
@click.option(
    "--reset",
    is_flag=True,
    default=False,
    help=(
        "Delete the selected fixture cohorts and their students first, then "
        "rebuild. Use when a distribution changed and stale progress would "
        "otherwise be kept. Only QA-owned rows are deleted."
    ),
)
def command(
    site_name: str, only: tuple[str, ...], long_course_quizzes: int, reset: bool
) -> None:
    """Build the report QA fixture matrix and its two permission users."""
    site: Site = _get_site(site_name)

    unknown = [key for key in only if key not in COHORTS_BY_KEY]
    if unknown:
        raise click.ClickException(
            f"Unknown fixture key(s): {unknown}. Available: {sorted(COHORTS_BY_KEY)}"
        )

    selected = [
        fixture for fixture in COHORT_FIXTURES if not only or fixture.key in only
    ]

    if reset:
        cohorts_deleted, students_deleted = _reset_fixtures(site, selected)
        click.secho(
            f"\nReset: deleted {students_deleted} fixture students and "
            f"{cohorts_deleted} rows for {len(selected)} cohort(s).",
            fg="yellow",
            bold=True,
        )

    needed_course_keys = {
        key
        for fixture in selected
        for key in (*fixture.course_keys, *fixture.inactive_course_keys)
    }

    click.secho("\n=== Building courses ===", fg="cyan", bold=True)
    for course_fixture in COURSE_FIXTURES:
        if course_fixture.key not in needed_course_keys:
            continue
        num_quizzes = (
            long_course_quizzes
            if course_fixture.key == "long"
            else course_fixture.num_quizzes
        )
        num_items = max(course_fixture.num_items, num_quizzes)
        course = build_report_course(
            site=site,
            course_key=course_fixture.key,
            num_items=num_items,
            num_quizzes=num_quizzes,
            questions_per_quiz=course_fixture.questions_per_quiz,
            big_quiz_questions=course_fixture.big_quiz_questions,
            pass_percentage=50,
            no_pass_mark_quiz=course_fixture.no_pass_mark_quiz,
            optional_last_question=course_fixture.optional_last_question,
        )
        items = course.viewable_items()
        click.secho(
            f"  {course.slug:<28} {len(items):>3} items, {num_quizzes:>2} quizzes"
            + (
                "  (first quiz has NO pass mark)"
                if course_fixture.no_pass_mark_quiz
                else ""
            )
            + (
                "  (last question of each quiz is OPTIONAL)"
                if course_fixture.optional_last_question
                else ""
            ),
            fg="green",
        )

    click.secho("\n=== Building cohorts ===", fg="cyan", bold=True)
    built: list[tuple[CohortFixture, Cohort]] = []
    for fixture in selected:
        cohort = build_report_cohort(
            site=site,
            cohort_name=fixture.cohort_name,
            num_students=fixture.num_students,
            course_slugs=tuple(COURSES_BY_KEY[key].slug for key in fixture.course_keys),
            inactive_course_slugs=tuple(
                COURSES_BY_KEY[key].slug for key in fixture.inactive_course_keys
            ),
            num_flagged=fixture.num_flagged,
            no_progress=fixture.no_progress,
            email_prefix=fixture.email_prefix,
            educator_email=EDUCATOR_EMAIL,
        )
        built.append((fixture, cohort))
        click.secho(
            f"  {fixture.key:<30} {fixture.num_students:>3} students  pk={cohort.pk}",
            fg="green",
        )

    click.secho("\n=== Permission users ===", fg="cyan", bold=True)
    educator = _get_or_create_user(site, EDUCATOR_EMAIL, "Quinn", "Reporter")
    click.secho(
        f"  Educator   {educator.email} / {educator.email} "
        f"(view_cohort on every fixture cohort built this run)",
        fg="green",
    )

    restricted = _get_or_create_user(site, RESTRICTED_EMAIL, "Robin", "Restricted")
    _grant_report_admin_access(restricted)
    permitted = next(
        (cohort for fixture, cohort in built if fixture.key == PERMITTED_FIXTURE_KEY),
        None,
    )
    if permitted is not None:
        assign_perm("view_cohort", restricted, permitted)
        click.secho(
            f"  Restricted {restricted.email} / {restricted.email} "
            f"(is_staff, view_cohort on '{permitted.name}' ONLY)",
            fg="green",
        )
        click.secho(
            "             every other cohort above is 'cohort B' for the "
            "403 / dropdown / forced-POST checks",
            fg="yellow",
        )
    else:
        click.secho(
            f"  Restricted {restricted.email} created but not scoped: fixture "
            f"'{PERMITTED_FIXTURE_KEY}' was not built this run.",
            fg="yellow",
        )

    click.secho("\n=== Fixture matrix ===", fg="cyan", bold=True)
    for fixture, cohort in built:
        courses = ", ".join(fixture.course_keys) or "none"
        inactive = ", ".join(fixture.inactive_course_keys)
        if inactive:
            courses = f"{courses} (+ {inactive} inactive)"
        click.echo(
            f"  {fixture.key:<30} {fixture.num_students:>3} students  "
            f"{courses:<28} {cohort.name}\n"
            f"  {'':<30} {fixture.purpose}"
        )
    click.secho(
        "\nSave each generated PDF as qa-artifacts/<fixture-key>.pdf.",
        fg="cyan",
        bold=True,
    )
