"""Seed the browser-QA data for the educator-interface small UI polish pass.

On the target site's ``demodev`` organisation it makes, idempotently:

* "QA Cohort A" (active, two learners), "QA Cohort B" (active, empty) and
  "QA Cohort Inactive" (inactive). None is registered for
  "Functionality Demo - Course Parts".
* "QA Learner One": an active learner of the organisation, in no QA cohort
  and with no direct registration for Course Parts.
* "QA Cohort Admin": ``cohort_admin`` on QA Cohort A only, no organisation
  role, with a verified email so the login goes straight through.
* A registration of QA Cohort B on "Forklift Safety Basics", a public course
  owned by Northwind Logistics. It is open to demodev but not available to
  it, so it is listed on demodev's Courses page only through that
  registration.
* "Question pool quiz" with its pass mark cleared, so a quiz with no pass
  mark exists. ``content_save`` of the demo content puts the mark back;
  re-run this command afterwards.
* "QA Two-page Survey": a ``CATEGORY_VALUE_SUM`` form with two pages and one
  multiple-choice question on each, appended as the last item of the
  "Wrapping Up" part of Course Parts. ``content_save`` of the demo content
  may drop the placement; re-run this command afterwards.

Every persona's password is ``demodev@email.com``.

Usage:
    uv run python manage.py qa_create_educator_small_polish_scenario
    uv run python manage.py qa_create_educator_small_polish_scenario --site-name DemoDev
"""

from __future__ import annotations

from typing import cast

import djclick as click

from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import ContentCollectionItemFactory
from freedom_ls.content_engine.models import (
    ContentCollectionItem,
    Course,
    CoursePart,
)
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
    QuestionOptionFactory,
)
from freedom_ls.form_engine.models import (
    Form,
    FormPage,
    FormQuestion,
    FormStrategy,
    QuestionType,
)
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    CohortMembership,
    Learner,
    LearnerCourseRegistration,
    StaffMember,
)
from freedom_ls.learner_management.queries import (
    is_course_available_to_organisation,
)
from freedom_ls.learner_management.utils import ensure_learner
from freedom_ls.organisations.models import Organisation
from freedom_ls.qa_helpers.management.commands.qa_create_organisation_scenarios import (
    PASSWORD,
    _ensure_cohort,
    _ensure_cohort_registration,
    _ensure_membership,
    _ensure_user,
    _get_course,
    _pin_current_site,
    _site_context,
)
from freedom_ls.role_based_permissions.models import ObjectRoleAssignment
from freedom_ls.role_based_permissions.utils import assign_object_role

ORG_SLUG = "demodev"
COURSE_PARTS_SLUG = "functionality-demo-course-parts"
UNAVAILABLE_COURSE_SLUG = "forklift-safety-basics"
UNGRADED_QUIZ_TITLE = "Question pool quiz"
SURVEY_PART_TITLE = "Wrapping Up"
SURVEY_TITLE = "QA Two-page Survey"
SURVEY_SLUG = "qa-two-page-survey"
SURVEY_OPTIONS = (("Not at all", "1"), ("Somewhat", "2"), ("Very", "3"))
# (page title, question text)
SURVEY_PAGES = (
    ("Your Pace", "How comfortable was the pace of the course?"),
    ("Your Confidence", "How confident do you feel applying what you learned?"),
)

COHORT_A = "QA Cohort A"
COHORT_B = "QA Cohort B"
COHORT_INACTIVE = "QA Cohort Inactive"
COHORT_A_MEMBERS = (
    ("qa-cohort-a-member-1@qa.test", "QA Member", "A1"),
    ("qa-cohort-a-member-2@qa.test", "QA Member", "A2"),
)
LEARNER_ONE = ("qa-learner-one@qa.test", "QA Learner", "One")
COHORT_ADMIN = ("qa-cohort-admin@qa.test", "QA Cohort", "Admin")


def _set_cohort_active(cohort: Cohort, is_active: bool) -> None:
    if cohort.is_active != is_active:
        cohort.is_active = is_active
        cohort.save(update_fields=["is_active"])


def _clear_pass_mark(site: Site, title: str) -> Form:
    quiz = cast(
        Form,
        Form._base_manager.get(site=site, title=title, strategy=FormStrategy.QUIZ),
    )
    if quiz.quiz_pass_percentage is not None:
        click.secho(
            f"Clearing pass mark of {quiz.title!r} pk={quiz.pk}: "
            f"{quiz.quiz_pass_percentage} -> None",
            fg="yellow",
        )
        Form._base_manager.filter(pk=quiz.pk).update(quiz_pass_percentage=None)
        quiz.refresh_from_db()
    return quiz


def _ensure_two_page_survey(site: Site) -> Form:
    """A two-page CATEGORY_VALUE_SUM form, one multiple-choice question a page."""
    existing = Form._base_manager.filter(site=site, slug=SURVEY_SLUG).first()
    if existing is not None:
        return cast(Form, existing)
    form = cast(
        Form,
        FormFactory(
            title=SURVEY_TITLE,
            slug=SURVEY_SLUG,
            strategy=FormStrategy.CATEGORY_VALUE_SUM,
            quiz_show_incorrect=None,
            quiz_pass_percentage=None,
            site=site,
        ),
    )
    for page_order, (page_title, text) in enumerate(SURVEY_PAGES):
        page = cast(
            FormPage,
            FormPageFactory(
                form=form,
                title=page_title,
                slug=f"{SURVEY_SLUG}-page-{page_order + 1}",
                order=page_order,
                category="Feedback",
                site=site,
            ),
        )
        question = cast(
            FormQuestion,
            FormQuestionFactory(
                form_page=page,
                question=text,
                type=QuestionType.MULTIPLE_CHOICE,
                required=True,
                order=0,
                site=site,
            ),
        )
        for order, (option_text, value) in enumerate(SURVEY_OPTIONS):
            QuestionOptionFactory(
                question=question,
                text=option_text,
                value=value,
                order=order,
                correct=None,
                site=site,
            )
    return form


def _get_course_part(site: Site, course: Course, title: str) -> CoursePart:
    part_ct = ContentType.objects.get_for_model(CoursePart)
    part_ids = ContentCollectionItem._base_manager.filter(
        site=site,
        collection_id=course.pk,
        child_type=part_ct,
    ).values_list("child_id", flat=True)
    part = CoursePart._base_manager.filter(
        site=site, pk__in=list(part_ids), title=title
    ).first()
    if part is None:
        raise click.ClickException(f"{course.title!r} has no part titled {title!r}.")
    return cast(CoursePart, part)


def _append_to_part(site: Site, part: CoursePart, form: Form) -> ContentCollectionItem:
    """Place ``form`` last in ``part``, once."""
    form_ct = ContentType.objects.get_for_model(Form)
    items = ContentCollectionItem._base_manager.filter(site=site, collection_id=part.pk)
    placed = items.filter(child_type=form_ct, child_id=form.pk).first()
    if placed is not None:
        return cast(ContentCollectionItem, placed)
    last = items.order_by("-order").values_list("order", flat=True).first()
    return cast(
        ContentCollectionItem,
        ContentCollectionItemFactory(
            collection_object=part,
            child_object=form,
            order=0 if last is None else last + 1,
            site=site,
        ),
    )


def _warn_on_course_parts(
    cohorts: list[Cohort], learner_one: User, course_parts: Course
) -> None:
    """Report, without removing, registrations that break the scenario."""
    for reg in CohortCourseRegistration._base_manager.filter(
        cohort__in=cohorts, course=course_parts
    ).select_related("cohort"):
        click.secho(
            f"WARNING: {reg.cohort.name!r} holds a Course Parts registration "
            f"pk={reg.pk} active={reg.is_active}",
            fg="red",
        )
    for lreg in LearnerCourseRegistration._base_manager.filter(
        learner__user=learner_one, course=course_parts
    ):
        click.secho(
            f"WARNING: QA Learner One holds a direct Course Parts registration "
            f"pk={lreg.pk} active={lreg.is_active}",
            fg="red",
        )
    for membership in CohortMembership._base_manager.filter(
        cohort__in=cohorts, learner__user=learner_one
    ).select_related("cohort"):
        click.secho(
            f"WARNING: QA Learner One is a member of {membership.cohort.name!r}",
            fg="red",
        )


@click.command()
@click.option("--site-name", default="DemoDev", help="Site name (default: DemoDev)")
def command(site_name: str) -> None:
    """Seed the educator small-UI-polish QA scenario."""
    site = Site.objects.get(name=site_name)
    _pin_current_site(site)
    with _site_context(site):
        org = cast(
            Organisation, Organisation._base_manager.get(site=site, slug=ORG_SLUG)
        )
        cohort_a = _ensure_cohort(site, org, COHORT_A)
        cohort_b = _ensure_cohort(site, org, COHORT_B)
        cohort_inactive = _ensure_cohort(site, org, COHORT_INACTIVE)
        for cohort in (cohort_a, cohort_b):
            _set_cohort_active(cohort, True)
        _set_cohort_active(cohort_inactive, False)
        cohorts = [cohort_a, cohort_b, cohort_inactive]

        members = [_ensure_user(site, *member) for member in COHORT_A_MEMBERS]
        for member in members:
            _ensure_membership(site, cohort_a, member)

        learner_one = _ensure_user(site, *LEARNER_ONE)
        ensure_learner(learner_one, org)

        cohort_admin = _ensure_user(site, *COHORT_ADMIN)
        assign_object_role(cohort_admin, cohort_a, "cohort_admin")

        unavailable = _get_course(site, UNAVAILABLE_COURSE_SLUG)
        if is_course_available_to_organisation(unavailable, org):
            raise click.ClickException(
                f"{unavailable.title!r} is available to {org.slug}; "
                "pick a course it is not available to."
            )
        _ensure_cohort_registration(site, cohort_b, unavailable)

        quiz = _clear_pass_mark(site, UNGRADED_QUIZ_TITLE)
        course_parts = _get_course(site, COURSE_PARTS_SLUG)
        _warn_on_course_parts(cohorts, learner_one, course_parts)

        survey = _ensure_two_page_survey(site)
        wrapping_up = _get_course_part(site, course_parts, SURVEY_PART_TITLE)
        survey_item = _append_to_part(site, wrapping_up, survey)
        part_outline = [
            (item.order, str(item.child))
            for item in ContentCollectionItem._base_manager.filter(
                site=site, collection_id=wrapping_up.pk
            ).order_by("order")
        ]
        survey_pages = list(
            FormPage._base_manager.filter(form=survey)
            .order_by("order")
            .values_list("title", "questions__question")
        )

    click.secho("--- Educator small polish QA data ---", fg="cyan", bold=True)
    click.echo(f"ORG {org.name!r} slug={org.slug} pk={org.pk}")
    for cohort in cohorts:
        emails = list(
            CohortMembership._base_manager.filter(cohort=cohort).values_list(
                "learner__user__email", flat=True
            )
        )
        regs = list(
            CohortCourseRegistration._base_manager.filter(cohort=cohort).values_list(
                "course__title", "is_active"
            )
        )
        click.echo(
            f"COHORT {cohort.name!r} pk={cohort.pk} active={cohort.is_active} "
            f"members={emails} registrations={regs}"
        )
    for user in [*members, learner_one, cohort_admin]:
        click.echo(
            f"USER {user.display_name!r} email={user.email} pk={user.pk} "
            f"password={PASSWORD} active={user.is_active}"
        )
    click.echo(
        f"LEARNER ONE learner rows="
        f"{list(Learner._base_manager.filter(user=learner_one).values_list('organisation__slug', 'is_active'))}"
    )
    grants = list(
        ObjectRoleAssignment._base_manager.filter(user=cohort_admin).values_list(
            "role", "content_type__model", "object_id", "is_active"
        )
    )
    org_ct = ContentType.objects.get_for_model(Organisation)
    org_grants = ObjectRoleAssignment._base_manager.filter(
        user=cohort_admin, content_type=org_ct, is_active=True
    ).count()
    staff = list(
        StaffMember._base_manager.filter(user=cohort_admin).values_list(
            "organisation__slug", "is_active"
        )
    )
    click.echo(
        f"COHORT ADMIN grants={grants} organisation_grants={org_grants} staff={staff}"
    )
    click.echo(
        f"UNAVAILABLE COURSE {unavailable.title!r} pk={unavailable.pk} "
        f"available={is_course_available_to_organisation(unavailable, org)}"
    )
    click.echo(
        f"NO PASS MARK QUIZ {quiz.title!r} pk={quiz.pk} "
        f"pass={quiz.quiz_pass_percentage}"
    )
    click.echo(
        f"SURVEY {survey.title!r} pk={survey.pk} strategy={survey.strategy} "
        f"pages={survey_pages}"
    )
    click.echo(
        f"SURVEY PLACEMENT part={wrapping_up.title!r} item pk={survey_item.pk} "
        f"order={survey_item.order} part outline={part_outline}"
    )
    click.echo(
        f"COURSE PARTS /educator/organisations/{org.slug}/courses/{course_parts.pk}"
    )
