"""Seed a CATEGORY_VALUE_SUM survey whose middle page is conditional.

Branch-logic QA needs a form where one page only appears when an earlier
answer opens its gate (``FormPage.condition_option``). Builds, idempotently:

1. Course "Branching survey course" whose only item is the form.
2. Form "Branching survey" (``CATEGORY_VALUE_SUM``, ``submit_on_exit=False``):
   - Page 1 "Setup" (``Core``): "Do you want the extra questions?"
     (slug ``want_extra``, Yes/No) and "How confident are you?" (1/2/3).
   - Page 2 "Extra" (``Extra``), gated on the Yes option of ``want_extra``:
     "How much extra?" (1/2/3) plus a FormContent block.
   - Page 3 "Wrap up" (``Core``): "How did it go?" (1/2/3).
3. Learner ``qa.branch@email.com`` (password == email), registered.

A fresh attempt later:
    uv run python manage.py qa_reset_learner_progress \
        --learner qa.branch@email.com --course-slug branching-survey-course

Usage:
    uv run python manage.py qa_create_branching_survey [--site-name DemoDev]
"""

from typing import cast

import djclick as click
from allauth.account.models import EmailAddress

from django.contrib.sites.models import Site

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
)
from freedom_ls.content_engine.models import Course
from freedom_ls.form_engine.factories import (
    FormContentFactory,
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
    QuestionOption,
    QuestionType,
)
from freedom_ls.learner_management.factories import LearnerCourseRegistrationFactory
from freedom_ls.learner_management.models import LearnerCourseRegistration
from freedom_ls.organisations.utils import get_default_organisation

LEARNER_EMAIL = "qa.branch@email.com"
COURSE_TITLE = "Branching survey course"
COURSE_SLUG = "branching-survey-course"
FORM_TITLE = "Branching survey"
FORM_SLUG = "branching-survey"

ONE_TWO_THREE = ["1", "2", "3"]


def _get_site(site_name: str) -> Site:
    try:
        return Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        available = list(Site.objects.values_list("name", flat=True))
        raise click.ClickException(
            f"Site '{site_name}' not found. Available: {available}"
        ) from e


def _get_or_create_learner(site: Site) -> tuple[User, bool]:
    existing: User | None = User.objects.filter(email=LEARNER_EMAIL).first()
    if existing is not None:
        existing.is_active = True
        existing.set_password(LEARNER_EMAIL)
        existing.save(update_fields=["is_active", "password"])
        learner, created = existing, False
    else:
        learner = cast(
            User,
            UserFactory(
                email=LEARNER_EMAIL,
                first_name="Branch",
                last_name="QA",
                is_active=True,
                password=LEARNER_EMAIL,
                site=site,
            ),
        )
        created = True
    EmailAddress.objects.update_or_create(
        user=learner,
        email=learner.email,
        defaults={"verified": True, "primary": True},
    )
    return learner, created


def _get_or_create_course(site: Site) -> Course:
    existing: Course | None = Course.objects.filter(slug=COURSE_SLUG, site=site).first()
    if existing is not None:
        return existing
    return cast(
        Course,
        CourseFactory(
            title=COURSE_TITLE,
            slug=COURSE_SLUG,
            description="QA course for conditional (branching) form pages.",
            site=site,
        ),
    )


def _page(form: Form, title: str, order: int, category: str, site: Site) -> FormPage:
    return cast(
        FormPage,
        FormPageFactory(
            form=form,
            title=title,
            slug=f"{FORM_SLUG}-page-{order + 1}",
            order=order,
            category=category,
            site=site,
        ),
    )


def _question(
    page: FormPage,
    text: str,
    order: int,
    options: list[tuple[str, str]],
    site: Site,
    slug: str = "",
) -> list[QuestionOption]:
    question = cast(
        FormQuestion,
        FormQuestionFactory(
            form_page=page,
            question=text,
            type=QuestionType.MULTIPLE_CHOICE,
            required=True,
            order=order,
            slug=slug,
            site=site,
        ),
    )
    return [
        cast(
            QuestionOption,
            QuestionOptionFactory(
                question=question,
                text=option_text,
                value=value,
                order=i,
                correct=None,
                site=site,
            ),
        )
        for i, (option_text, value) in enumerate(options)
    ]


def _build_form(site: Site) -> Form:
    existing: Form | None = Form.objects.filter(slug=FORM_SLUG, site=site).first()
    if existing is not None:
        return existing

    form = cast(
        Form,
        FormFactory(
            title=FORM_TITLE,
            slug=FORM_SLUG,
            strategy=FormStrategy.CATEGORY_VALUE_SUM,
            submit_on_exit=False,
            quiz_show_incorrect=None,
            quiz_pass_percentage=None,
            site=site,
        ),
    )

    setup = _page(form, "Setup", 0, "Core", site)
    yes_option, _no_option = _question(
        setup,
        "Do you want the extra questions?",
        0,
        [("Yes", "yes"), ("No", "no")],
        site,
        slug="want_extra",
    )
    _question(
        setup,
        "How confident are you?",
        1,
        list(zip(["Low", "Medium", "High"], ONE_TWO_THREE, strict=True)),
        site,
    )

    extra = _page(form, "Extra", 1, "Extra", site)
    extra.condition_option = yes_option
    extra.save(update_fields=["condition_option"])
    _question(
        extra,
        "How much extra?",
        0,
        list(zip(["A little", "Some", "A lot"], ONE_TWO_THREE, strict=True)),
        site,
    )
    FormContentFactory(
        form_page=extra,
        content="These only apply if you asked for them.",
        order=1,
        site=site,
    )

    wrap_up = _page(form, "Wrap up", 2, "Core", site)
    _question(
        wrap_up,
        "How did it go?",
        0,
        list(zip(["Badly", "Fine", "Well"], ONE_TWO_THREE, strict=True)),
        site,
    )
    return form


def _attach_to_course(course: Course, form: Form, site: Site) -> None:
    if not any(item.child_id == form.pk for item in course.items.all()):
        ContentCollectionItemFactory(
            collection_object=course, child_object=form, order=0, site=site
        )


def _register(learner: User, course: Course, site: Site) -> None:
    if not LearnerCourseRegistration.objects.filter(
        learner__user=learner, course=course, site=site
    ).exists():
        LearnerCourseRegistrationFactory(
            learner__user=learner,
            learner__organisation=get_default_organisation(site),
            course=course,
            site=site,
        )


@click.command()
@click.option(
    "--site-name",
    default="DemoDev",
    help="Site name to create the data on (default: 'DemoDev').",
)
def command(site_name: str) -> None:
    """Seed the branching survey course, form and its QA learner."""
    site = _get_site(site_name)
    learner, created = _get_or_create_learner(site)
    course = _get_or_create_course(site)
    form = _build_form(site)
    _attach_to_course(course, form, site)
    _register(learner, course, site)

    click.secho("\n--- Branching survey (conditional pages) ---", fg="cyan", bold=True)
    click.secho(f"Site:   {site.name} ({site.domain}) [id {site.pk}]", fg="cyan")
    click.secho(
        f"{'Created' if created else 'Reused'} learner: "
        f"{learner.email} / {learner.email} [pk {learner.pk}]",
        fg="green",
    )
    click.secho(f"Course: {course.title} [pk {course.pk}, slug {course.slug}]")
    click.secho(
        f"Form:   {form.title} [pk {form.pk}, strategy {form.strategy}, "
        f"submit_on_exit {form.submit_on_exit}]"
    )
    click.secho(f"Course home: /courses/{course.slug}/", fg="green", bold=True)
    click.secho(f"Form start : /courses/{course.slug}/1/", fg="green")
    for page in form.pages.select_related("condition_option__question"):
        gate = (
            f" gated on '{page.condition_option.question.slug}' = "
            f"{page.condition_option.value}"
            if page.condition_option
            else ""
        )
        click.echo(f"  p{page.order + 1} {page.title} [{page.category}]{gate}")
        for child in page.children():
            click.echo(f"     - {child}")
