"""Seed three application-gated edge-case courses for the anonymous apply journey.

Creates (idempotently) on a single site (default: DemoDev):

1. "QA page-one file course" -- its application form has exactly ONE page with a
   required short-text question "Your name" and a required file-upload question
   "Upload your ID". It exists to show a file question on the first form page,
   reached straight after About you.
2. "QA page-less course" -- its application form has NO pages at all.
3. "QA hidden gated course" -- visibility=hidden, bound to the same demo
   application form as "Functionality Demo - Application gated course".

The gating fields (access_config + application_form FK) mirror the demo gated
course. Course 3 copies the demo course's access_config verbatim (it shares the
demo form); courses 1 and 2 use {"access_type": "application_gated"} because
their forms have no source file for the access_config path to name (the path
is only read by the content loader, never at runtime).

Each course carries one Topic, like the demo gated course, so its TOC renders.

Usage:
    uv run python manage.py qa_create_anon_apply_edge_courses
    uv run python manage.py qa_create_anon_apply_edge_courses --site-name DemoDev
"""

from typing import cast

import djclick as click

from django.contrib.sites.models import Site

from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.content_engine.models import Course, CourseVisibility, Topic
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
)
from freedom_ls.form_engine.models import (
    Form,
    FormPage,
    FormQuestion,
    FormStrategy,
    QuestionType,
)
from freedom_ls.qa_helpers.management.commands.qa_create_form_question_types import (
    _get_site,
)
from freedom_ls.qa_helpers.management.commands.qa_create_report_course import (
    _lay_out_course,
)

DEMO_GATED_COURSE_SLUG = "functionality-demo-application-gated-course"
GATED_ACCESS_CONFIG: dict[str, str] = {"access_type": "application_gated"}

PAGE_ONE_COURSE_TITLE = "QA page-one file course"
PAGE_ONE_COURSE_SLUG = "qa-page-one-file-course"
PAGE_ONE_FORM_TITLE = "QA page-one file application form"
PAGE_ONE_FORM_SLUG = "qa-page-one-file-application-form"
PAGE_ONE_PAGE_TITLE = "Your background"
PAGE_ONE_PAGE_SLUG = "qa-page-one-file-your-background"
PAGE_ONE_QUESTIONS: list[tuple[str, QuestionType]] = [
    ("Your name", QuestionType.SHORT_TEXT),
    ("Upload your ID", QuestionType.FILE_UPLOAD),
]

PAGELESS_COURSE_TITLE = "QA page-less course"
PAGELESS_COURSE_SLUG = "qa-page-less-course"
PAGELESS_FORM_TITLE = "QA page-less application form"
PAGELESS_FORM_SLUG = "qa-page-less-application-form"

HIDDEN_COURSE_TITLE = "QA hidden gated course"
HIDDEN_COURSE_SLUG = "qa-hidden-gated-course"


def _get_demo_gated_course(site: Site) -> Course:
    course: Course | None = Course.objects.filter(
        slug=DEMO_GATED_COURSE_SLUG, site=site
    ).first()
    if course is None or course.application_form is None:
        raise click.ClickException(
            f"Demo course '{DEMO_GATED_COURSE_SLUG}' (with an application form) not "
            f"found on site '{site.name}'. Run `content_save demo_content "
            f"{site.name}` first."
        )
    return course


def _get_or_create_form(site: Site, title: str, slug: str) -> Form:
    existing: Form | None = Form.objects.filter(slug=slug, site=site).first()
    if existing is not None:
        return existing
    return cast(
        Form,
        FormFactory(title=title, slug=slug, strategy=FormStrategy.UNSCORED, site=site),
    )


def _build_page_one_form(site: Site) -> Form:
    """One page; required short-text then required file-upload. Idempotent."""
    form = _get_or_create_form(site, PAGE_ONE_FORM_TITLE, PAGE_ONE_FORM_SLUG)
    page: FormPage | None = FormPage.objects.filter(form=form, site=site).first()
    if page is None:
        page = cast(
            FormPage,
            FormPageFactory(
                form=form,
                title=PAGE_ONE_PAGE_TITLE,
                slug=PAGE_ONE_PAGE_SLUG,
                order=0,
                site=site,
            ),
        )
    for order, (text, qtype) in enumerate(PAGE_ONE_QUESTIONS):
        if not FormQuestion.objects.filter(
            form_page=page, question=text, site=site
        ).exists():
            FormQuestionFactory(
                form_page=page,
                question=text,
                type=qtype,
                required=True,
                order=order,
                site=site,
            )
    return form


def _get_or_create_course(
    site: Site,
    title: str,
    slug: str,
    form: Form,
    access_config: dict[str, str],
    visibility: str,
) -> Course:
    """Create the gated course, or re-assert the gating fields on an existing one."""
    existing: Course | None = Course.objects.filter(slug=slug, site=site).first()
    if existing is not None:
        existing.title = title
        existing.access_config = access_config
        existing.application_form = form
        existing.visibility = visibility
        existing.save(
            update_fields=["title", "access_config", "application_form", "visibility"]
        )
        return existing
    return cast(
        Course,
        CourseFactory(
            title=title,
            slug=slug,
            description="QA edge case for the anonymous course-application journey.",
            access_config=access_config,
            application_form=form,
            visibility=visibility,
            site=site,
        ),
    )


def _ensure_welcome_topic(course: Course, site: Site) -> None:
    slug = f"{course.slug}-welcome"
    topic: Topic | None = Topic.objects.filter(slug=slug, site=site).first()
    if topic is None:
        topic = cast(
            Topic,
            TopicFactory(
                title="Welcome",
                slug=slug,
                content="# Welcome\n\nYou have been accepted onto this course.\n",
                site=site,
            ),
        )
    _lay_out_course(course, [topic], site)


def _report(course: Course) -> None:
    form = cast(Form, course.application_form)
    pages = FormPage.objects.filter(form=form).order_by("order")
    click.secho(f"\nCourse: {course.title}", fg="cyan", bold=True)
    click.echo(f"  pk={course.pk}  slug={course.slug}  visibility={course.visibility}")
    click.echo(f"  access_config={course.access_config}")
    click.echo(f"  /courses/{course.slug}/")
    click.echo(f"  form: {form.title}  pk={form.pk}  slug={form.slug}")
    click.echo(f"  pages: {pages.count()}")
    for page in pages:
        for q in FormQuestion.objects.filter(form_page=page).order_by("order"):
            click.echo(
                f"    [{page.title}] {q.question}  type={q.type} required={q.required}"
            )


@click.command()
@click.option(
    "--site-name",
    default="DemoDev",
    help="Site name to create the data on (default: 'DemoDev').",
)
def command(site_name: str) -> None:
    """Seed the three anonymous-apply edge-case courses."""
    site = _get_site(site_name)
    demo_course = _get_demo_gated_course(site)
    demo_form = cast(Form, demo_course.application_form)

    page_one_course = _get_or_create_course(
        site,
        PAGE_ONE_COURSE_TITLE,
        PAGE_ONE_COURSE_SLUG,
        _build_page_one_form(site),
        GATED_ACCESS_CONFIG,
        demo_course.visibility,
    )
    pageless_course = _get_or_create_course(
        site,
        PAGELESS_COURSE_TITLE,
        PAGELESS_COURSE_SLUG,
        _get_or_create_form(site, PAGELESS_FORM_TITLE, PAGELESS_FORM_SLUG),
        GATED_ACCESS_CONFIG,
        demo_course.visibility,
    )
    hidden_course = _get_or_create_course(
        site,
        HIDDEN_COURSE_TITLE,
        HIDDEN_COURSE_SLUG,
        demo_form,
        dict(demo_course.access_config),
        CourseVisibility.HIDDEN,
    )

    for course in (page_one_course, pageless_course, hidden_course):
        _ensure_welcome_topic(course, site)

    click.secho(
        f"--- Anonymous-apply edge courses on {site.name} ({site.domain}) ---",
        fg="green",
        bold=True,
    )
    for course in (page_one_course, pageless_course, hidden_course):
        _report(course)
