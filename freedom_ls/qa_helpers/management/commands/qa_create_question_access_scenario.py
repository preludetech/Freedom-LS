"""Seed the browser-QA data set for the question_bank_viewer access feature.

Run after ``create_demo_data``, ``qa_create_course_content_preview`` and
``qa_create_attempt_review_scenario``: it builds on "QA Preview Course" and the
``demodev`` organisation they leave behind. Idempotent, on one site (default
DemoDev), in the organisation given by ``--organisation-slug`` (default
``demodev``):

1. Staff personas, password ``testpass123``, each an active StaffMember:

   - ``qa.nonholder@qa.test``: organisation_admin, never question_bank_viewer.
   - ``qa.holder@qa.test``: organisation_admin; QA grants question_bank_viewer
     through the UI.
   - ``qa.third@qa.test``: organisation_admin; QA grants question_bank_viewer
     and then deactivates it.
   - ``qa.cohortadmin@qa.test``: cohort_admin on "QA Preview Cohort" only.
   - ``qa.qbvonly@qa.test``: question_bank_viewer on the organisation and no
     other role.

   Grants go through ``role_assignment.assign_role`` with the site's superuser
   as grantor. A re-run deactivates any question_bank_viewer grant a QA run
   left on the first four, and reactivates every persona's StaffMember row.

2. "QA Preview Course" gains a two-page quiz ("QA Multi-page quiz", top level)
   and a reference part ("QA Reference material") holding a single-page quiz
   ("QA Reference quiz"), beside the single-page "Module quiz" already inside
   the "Module one" part. Their slugs carry the course-slug prefix, so
   ``qa_create_course_content_preview`` removes them with the rest.

3. Two report cohorts registered on "QA Preview Course", built by
   ``qa_create_report_cohort``'s ``build_report_cohort``: "QA Report Cohort"
   (six learners, some quiz answers wrong, so the Report tab shows quiz
   confusion cards) and "QA Report Clean Cohort" (one learner who answers
   every quiz question correctly).

4. A survey answer with an uploaded file: the "Upload your notes" question
   of the course's "Feedback survey", on a completed sitting of a
   "QA Report Cohort" learner.

Usage:
    uv run python manage.py qa_create_question_access_scenario
    uv run python manage.py qa_create_question_access_scenario --organisation-slug demodev
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import djclick as click

from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.core.files.base import ContentFile
from django.db import transaction

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import (
    CoursePartFactory,
    CourseReferencePartFactory,
)
from freedom_ls.content_engine.models import (
    ContentCollectionItem,
    Course,
    CoursePart,
    CourseReferencePart,
)
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    QuestionAnswerFactory,
    QuestionAnswerFileFactory,
)
from freedom_ls.form_engine.models import (
    Form,
    FormPage,
    FormProgress,
    FormQuestion,
    FormStrategy,
    QuestionAnswer,
    QuestionAnswerFile,
    QuestionType,
)
from freedom_ls.learner_management.models import Cohort, StaffMember
from freedom_ls.learner_management.role_assignment import (
    assign_role,
    deactivate_role,
    set_staff_member_active,
)
from freedom_ls.learner_management.utils import ensure_staff_member
from freedom_ls.organisations.models import Organisation
from freedom_ls.qa_helpers.management.commands.qa_create_course_content_preview import (
    DEMODEV_COHORT,
    PREVIEW_SLUG,
    _ensure_cohort,
    _ensure_user,
    _options,
    _pdf_bytes,
    _place,
    _question,
)
from freedom_ls.qa_helpers.management.commands.qa_create_organisation_scenarios import (
    _pin_current_site,
    _site_context,
)
from freedom_ls.qa_helpers.management.commands.qa_create_report_cohort import (
    build_report_cohort,
)
from freedom_ls.role_based_permissions.models import ObjectRoleAssignment

SUPERUSER_EMAIL = "demodev@email.com"
QUESTION_ROLE = "question_bank_viewer"
REPORT_COHORT = "QA Report Cohort"
CLEAN_COHORT = "QA Report Clean Cohort"
REPORT_PREFIX = "qa-qaccess-report"
CLEAN_PREFIX = "qa-qaccess-clean"
UPLOAD_QUESTION = "Upload your notes"
UPLOAD_FILENAME = "qa-survey-notes.pdf"


@dataclass(frozen=True)
class Persona:
    email: str
    first: str
    last: str
    organisation_role: str | None


PERSONAS = (
    Persona("qa.nonholder@qa.test", "Nolan", "Nonholder", "organisation_admin"),
    Persona("qa.holder@qa.test", "Hana", "Holder", "organisation_admin"),
    Persona("qa.third@qa.test", "Thandi", "Third", "organisation_admin"),
    Persona("qa.cohortadmin@qa.test", "Colin", "Cohortadmin", None),
    Persona("qa.qbvonly@qa.test", "Quinton", "Qbvonly", QUESTION_ROLE),
)


# --------------------------------------------------------------------------
# People
# --------------------------------------------------------------------------


def _clear_question_role(grantor: User, user: User, org: Organisation) -> None:
    org_ct = ContentType.objects.get_for_model(Organisation)
    if ObjectRoleAssignment._base_manager.filter(
        user=user,
        content_type=org_ct,
        object_id=str(org.pk),
        role=QUESTION_ROLE,
        is_active=True,
    ).exists():
        click.secho(f"Deactivating {QUESTION_ROLE} of {user.email}", fg="yellow")
        deactivate_role(grantor, user, QUESTION_ROLE, org, reason="QA scenario reset")


def _ensure_persona(
    site: Site, grantor: User, org: Organisation, cohort: Cohort, persona: Persona
) -> User:
    user = _ensure_user(site, persona.email, persona.first, persona.last)
    staff_member = ensure_staff_member(user, org)
    if not staff_member.is_active:
        set_staff_member_active(grantor, staff_member, True, reason="QA scenario reset")
    if persona.organisation_role is None:
        assign_role(grantor, user, "cohort_admin", cohort)
    else:
        assign_role(grantor, user, persona.organisation_role, org)
    if persona.organisation_role != QUESTION_ROLE:
        _clear_question_role(grantor, user, org)
    return user


# --------------------------------------------------------------------------
# Course outline
# --------------------------------------------------------------------------


def _new_quiz(site: Site, slug: str, title: str, file_path: str) -> Form:
    return cast(
        Form,
        FormFactory(
            title=title,
            slug=slug,
            file_path=file_path,
            strategy=FormStrategy.QUIZ,
            quiz_pass_percentage=50,
            quiz_show_incorrect=True,
            content=f"{title}: answer every question.",
            site=site,
        ),
    )


def _new_page(site: Site, form: Form, title: str, order: int) -> FormPage:
    return cast(
        FormPage,
        FormPageFactory(
            form=form,
            title=title,
            slug=f"{form.slug}-p{order + 1}",
            order=order,
            site=site,
        ),
    )


def _ensure_multi_page_quiz(site: Site, course: Course) -> Form:
    slug = f"{PREVIEW_SLUG}-multi-page-quiz"
    existing: Form | None = Form._base_manager.filter(site=site, slug=slug).first()
    if existing is not None:
        return existing
    form = _new_quiz(
        site, slug, "QA Multi-page quiz", f"{PREVIEW_SLUG}/multi_page_quiz.md"
    )
    page1 = _new_page(site, form, "Instruments", 0)
    altimeter = _question(
        site,
        page1,
        "Which instrument shows the aircraft's altitude above sea level?",
        QuestionType.MULTIPLE_CHOICE,
        0,
    )
    _options(
        site,
        altimeter,
        [("Altimeter", True), ("Tachometer", False), ("Magnetic compass", False)],
    )
    page2 = _new_page(site, form, "Weather", 1)
    cloud = _question(
        site,
        page2,
        "Which cloud type is most associated with thunderstorms?",
        QuestionType.MULTIPLE_CHOICE,
        0,
    )
    _options(
        site,
        cloud,
        [("Cumulonimbus", True), ("Cirrus", False), ("Stratus", False)],
    )
    visibility = _question(
        site,
        page2,
        "Which of these reduce visibility?",
        QuestionType.CHECKBOXES,
        1,
    )
    _options(
        site,
        visibility,
        [("Fog", True), ("Haze", True), ("Clear sunshine", False)],
    )
    last_order = (
        ContentCollectionItem._base_manager.filter(collection_id=course.pk)
        .order_by("-order")
        .values_list("order", flat=True)
        .first()
    )
    _place(site, course, form, (last_order or 0) + 1)
    return form


def _ensure_reference_quiz(site: Site, course: Course) -> Form:
    part_slug = f"{PREVIEW_SLUG}-reference-material"
    part: CoursePart | None = CoursePart._base_manager.filter(
        site=site, slug=part_slug
    ).first()
    if part is None:
        part = cast(
            CoursePart,
            CoursePartFactory(
                title="QA Reference material",
                slug=part_slug,
                file_path=f"{PREVIEW_SLUG}/reference_material",
                site=site,
            ),
        )
    if not CourseReferencePart._base_manager.filter(
        course=course, course_part=part
    ).exists():
        CourseReferencePartFactory(course=course, course_part=part, order=0, site=site)

    slug = f"{PREVIEW_SLUG}-reference-quiz"
    existing: Form | None = Form._base_manager.filter(site=site, slug=slug).first()
    if existing is not None:
        return existing
    form = _new_quiz(
        site,
        slug,
        "QA Reference quiz",
        f"{PREVIEW_SLUG}/reference_material/quiz.md",
    )
    page = _new_page(site, form, "Abbreviations", 0)
    vfr = _question(
        site,
        page,
        "What does the abbreviation VFR stand for?",
        QuestionType.MULTIPLE_CHOICE,
        0,
    )
    _options(
        site,
        vfr,
        [
            ("Visual Flight Rules", True),
            ("Very Fast Rotation", False),
            ("Vertical Flight Range", False),
        ],
    )
    _place(site, part, form, 0)
    return form


# --------------------------------------------------------------------------
# Survey answer with a file
# --------------------------------------------------------------------------


def _ensure_survey_file(site: Site, cohort: Cohort) -> QuestionAnswerFile | None:
    question: FormQuestion | None = (
        FormQuestion._base_manager.filter(
            site=site,
            question=UPLOAD_QUESTION,
            form_page__form__slug=f"{PREVIEW_SLUG}-feedback-survey",
        )
        .select_related("form_page__form")
        .first()
    )
    if question is None:
        return None
    sitting: FormProgress | None = (
        FormProgress._base_manager.filter(
            form=question.form_page.form,
            completed_time__isnull=False,
            user__learner__cohortmembership__cohort=cohort,
        )
        .order_by("completed_time")
        .first()
    )
    if sitting is None:
        return None
    answer = QuestionAnswer._base_manager.filter(
        form_progress=sitting, question=question
    ).first()
    if answer is None:
        answer = cast(
            QuestionAnswer,
            QuestionAnswerFactory(form_progress=sitting, question=question, site=site),
        )
    existing: QuestionAnswerFile | None = QuestionAnswerFile._base_manager.filter(
        answer=answer
    ).first()
    if existing is not None:
        return existing
    return cast(
        QuestionAnswerFile,
        QuestionAnswerFileFactory(
            answer=answer,
            original_filename=UPLOAD_FILENAME,
            file=ContentFile(_pdf_bytes(), name="notes.pdf"),
            site=site,
        ),
    )


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------


def _describe_form(form: Form, where: str) -> None:
    pages = list(FormPage._base_manager.filter(form=form).order_by("order"))
    click.echo(f"QUIZ {form.title!r} pk={form.pk} pages={len(pages)} where={where}")
    for question in FormQuestion._base_manager.filter(form_page__form=form).order_by(
        "form_page__order", "order"
    ):
        options = list(
            question.options.order_by("order").values_list("text", "correct")
        )
        click.echo(f"    Q {question.question!r} options={options}")


def _report(
    org: Organisation,
    users: list[User],
    cohort: Cohort,
    report_cohort: Cohort,
    clean_cohort: Cohort,
    course: Course,
    quizzes: list[tuple[Form, str]],
    answer_file: QuestionAnswerFile | None,
) -> None:
    click.secho("--- Question access QA data ---", fg="cyan", bold=True)
    click.echo(f"ORG {org.name!r} slug={org.slug} pk={org.pk}")
    for user in users:
        staff = StaffMember._base_manager.get(user=user, organisation=org)
        roles = list(
            ObjectRoleAssignment._base_manager.filter(user=user, is_active=True)
            .order_by("role")
            .values_list("role", flat=True)
        )
        click.echo(
            f"USER {user.email} / testpass123 pk={user.pk} "
            f"staff_active={staff.is_active} superuser={user.is_superuser} roles={roles}"
        )
    click.echo(f"COHORT_ADMIN_COHORT {cohort.name!r} pk={cohort.pk}")
    click.echo(f"COURSE {course.title!r} pk={course.pk}")
    for form, where in quizzes:
        _describe_form(form, where)
    for label, c in (("REPORT", report_cohort), ("CLEAN", clean_cohort)):
        click.echo(
            f"{label}_COHORT {c.name!r} pk={c.pk} "
            f"/educator/organisations/{org.slug}/cohorts/{c.pk}"
        )
    if answer_file is None:
        click.secho("No survey answer file could be made", fg="red")
    else:
        click.echo(
            f"QUESTION_ANSWER_FILE pk={answer_file.pk} answer={answer_file.answer_id} "
            f"form_progress={answer_file.answer.form_progress_id}"
        )


@click.command()
@click.option("--site-name", default="DemoDev", show_default=True)
@click.option("--organisation-slug", default="demodev", show_default=True)
def command(site_name: str, organisation_slug: str) -> None:
    """Seed the question access QA scenario."""
    try:
        site = Site.objects.get(name=site_name)
        org = Organisation._base_manager.get(site=site, slug=organisation_slug)
        course = Course._base_manager.get(site=site, slug=PREVIEW_SLUG)
    except (Site.DoesNotExist, Organisation.DoesNotExist, Course.DoesNotExist) as e:
        raise click.ClickException(
            f"{e} Run create_demo_data and qa_create_course_content_preview first."
        ) from e
    grantor: User | None = User._base_manager.filter(
        site=site, email=SUPERUSER_EMAIL, is_superuser=True
    ).first()
    if grantor is None:
        raise click.ClickException(f"Superuser {SUPERUSER_EMAIL} not found.")

    _pin_current_site(site)
    with _site_context(site), transaction.atomic():
        cohort = _ensure_cohort(site, org, DEMODEV_COHORT)
        users = [_ensure_persona(site, grantor, org, cohort, p) for p in PERSONAS]

        multi = _ensure_multi_page_quiz(site, course)
        reference = _ensure_reference_quiz(site, course)
        module_quiz = Form._base_manager.get(
            site=site, slug=f"{PREVIEW_SLUG}-module-quiz"
        )

        report_cohort = build_report_cohort(
            site=site,
            cohort_name=REPORT_COHORT,
            num_learners=6,
            course_slugs=(PREVIEW_SLUG,),
            inactive_course_slugs=(),
            num_flagged=0,
            no_progress=False,
            email_prefix=REPORT_PREFIX,
            educator_email=None,
            organisation=org,
        )
        clean_cohort = build_report_cohort(
            site=site,
            cohort_name=CLEAN_COHORT,
            num_learners=1,
            course_slugs=(PREVIEW_SLUG,),
            inactive_course_slugs=(),
            num_flagged=0,
            no_progress=False,
            email_prefix=CLEAN_PREFIX,
            educator_email=None,
            organisation=org,
        )
        answer_file = _ensure_survey_file(site, report_cohort)

        _report(
            org,
            users,
            cohort,
            report_cohort,
            clean_cohort,
            course,
            [
                (module_quiz, "inside part 'Module one'"),
                (multi, "top level of the course"),
                (reference, "reference part 'QA Reference material'"),
            ],
            answer_file,
        )
