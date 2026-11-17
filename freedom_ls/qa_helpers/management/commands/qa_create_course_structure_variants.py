"""Seed courses with unusual outline shapes for educator-interface QA.

Delete-and-recreate by slug, so it can be re-run. Run
``qa_create_course_content_preview`` first: it creates "QA Preview Cohort",
which every course here is registered to, so each one shows in the dev
organisation's educator Courses list.

Builds on the site (default DemoDev):

- "QA Multi Page Course": topic "Introduction", form "Three page survey"
  (three unconditional pages "First page", "Second page", "Third page") and
  form "One page survey" (one page "Only page").
- "QA Long Course": 13 top-level items. Items 1-8 and 10-12 are topics
  "Topic 1".."Topic 11"; item 9 is part "Long part" holding "Part topic A",
  "Part topic B", "Part topic C"; item 13 is part "Outer part" holding part
  "Inner part" holding topic "Nested topic".

Usage:
    uv run python manage.py qa_create_course_structure_variants [--site-name DemoDev]
"""

from __future__ import annotations

from typing import cast
from uuid import UUID

import djclick as click

from django.contrib.sites.models import Site
from django.db import transaction

from freedom_ls.content_engine.factories import CoursePartFactory
from freedom_ls.content_engine.models import (
    ContentCollectionItem,
    Course,
    CoursePart,
    Topic,
)
from freedom_ls.form_engine.factories import FormFactory, FormPageFactory
from freedom_ls.form_engine.models import (
    Form,
    FormPage,
    FormProgress,
    FormStrategy,
    QuestionType,
)
from freedom_ls.learner_management.factories import CohortCourseRegistrationFactory
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    LearnerCourseRegistration,
)
from freedom_ls.learner_progress.models import CourseProgress, TopicProgress
from freedom_ls.organisations.models import Organisation
from freedom_ls.qa_helpers.management.commands.qa_create_course_content_preview import (
    DEMODEV_COHORT,
    DEMODEV_ORG_SLUG,
    _course,
    _place,
    _question,
    _topic,
)
from freedom_ls.qa_helpers.management.commands.qa_create_organisation_scenarios import (
    _pin_current_site,
    _site_context,
)

MULTI_PAGE_SLUG = "qa-multi-page-course"
LONG_SLUG = "qa-long-course"
ALL_SLUGS = (MULTI_PAGE_SLUG, LONG_SLUG)
LONG_TOPIC_COUNT = 11
LONG_PART_POSITION = 9  # 1-based top-level position of "Long part"


def _purge(site: Site) -> None:
    """Delete every course this command owns and everything hanging off it."""
    for slug in ALL_SLUGS:
        course = Course._base_manager.filter(site=site, slug=slug).first()
        if course is None:
            continue
        click.echo(f"Removing course {course.pk} '{course}' ({slug})")
        for model in (
            CourseProgress,
            LearnerCourseRegistration,
            CohortCourseRegistration,
        ):
            result = model._base_manager.filter(course=course).delete()
            if result[0]:
                click.echo(f"  {model.__name__}: {result}")
        items = ContentCollectionItem._base_manager.filter(
            collection_id=course.pk
        ).delete()
        click.echo(f"  Course items: {items}")
        click.echo(f"  Course: {course.delete()}")
        prefix = f"{slug}-"
        for part in CoursePart._base_manager.filter(site=site, slug__startswith=prefix):
            items = ContentCollectionItem._base_manager.filter(
                collection_id=part.pk
            ).delete()
            click.echo(f"  Part {part.pk} '{part}': items {items}, {part.delete()}")
        for topic in Topic._base_manager.filter(site=site, slug__startswith=prefix):
            progress = TopicProgress._base_manager.filter(topic=topic).delete()
            click.echo(
                f"  Topic {topic.pk} '{topic}': progress {progress}, {topic.delete()}"
            )
        for form in Form._base_manager.filter(site=site, slug__startswith=prefix):
            progress = FormProgress._base_manager.filter(form=form).delete()
            click.echo(
                f"  Form {form.pk} '{form}': progress {progress}, {form.delete()}"
            )


def _part(site: Site, prefix: str, key: str, title: str) -> CoursePart:
    return cast(
        CoursePart,
        CoursePartFactory(
            title=title,
            slug=f"{prefix}-{key}",
            file_path=f"{prefix}/{key}",
            site=site,
        ),
    )


def _unscored_form(
    site: Site, prefix: str, key: str, title: str, page_titles: list[str]
) -> Form:
    form = cast(
        Form,
        FormFactory(
            title=title,
            slug=f"{prefix}-{key}",
            file_path=f"{prefix}/{key}.md",
            strategy=FormStrategy.UNSCORED,
            quiz_show_incorrect=None,
            quiz_pass_percentage=None,
            content=f"{title}: answer each page.",
            site=site,
        ),
    )
    for order, page_title in enumerate(page_titles):
        page = cast(
            FormPage,
            FormPageFactory(
                form=form,
                title=page_title,
                slug=f"{prefix}-{key}-p{order + 1}",
                order=order,
                site=site,
            ),
        )
        _question(
            site,
            page,
            f"What did you think of {page_title.lower()}?",
            QuestionType.LONG_TEXT,
            0,
        )
    return form


def _build_multi_page(site: Site) -> Course:
    course = _course(site, "QA Multi Page Course", MULTI_PAGE_SLUG)
    prefix = course.slug
    intro = _topic(site, prefix, "01_intro", "Introduction", "Welcome to the course.")
    _place(site, course, intro, 0)
    three = _unscored_form(
        site,
        prefix,
        "three-page-survey",
        "Three page survey",
        ["First page", "Second page", "Third page"],
    )
    _place(site, course, three, 1)
    one = _unscored_form(
        site, prefix, "one-page-survey", "One page survey", ["Only page"]
    )
    _place(site, course, one, 2)
    return course


def _build_long(site: Site) -> Course:
    course = _course(site, "QA Long Course", LONG_SLUG)
    prefix = course.slug
    order = 0
    for n in range(1, LONG_TOPIC_COUNT + 1):
        if order == LONG_PART_POSITION - 1:
            part = _part(site, prefix, "long-part", "Long part")
            _place(site, course, part, order)
            order += 1
            for i, letter in enumerate("ABC"):
                topic = _topic(
                    site,
                    prefix,
                    f"part-topic-{letter.lower()}",
                    f"Part topic {letter}",
                    f"Part topic {letter} inside Long part.",
                )
                _place(site, part, topic, i)
        topic = _topic(site, prefix, f"topic-{n:02d}", f"Topic {n}", f"Topic {n}.")
        _place(site, course, topic, order)
        order += 1
    outer = _part(site, prefix, "outer-part", "Outer part")
    _place(site, course, outer, order)
    inner = _part(site, prefix, "inner-part", "Inner part")
    _place(site, outer, inner, 0)
    nested = _topic(
        site, prefix, "nested-topic", "Nested topic", "A topic two parts deep."
    )
    _place(site, inner, nested, 0)
    return course


def _outline(collection_id: UUID, depth: int = 1) -> None:
    for item in ContentCollectionItem._base_manager.filter(
        collection_id=collection_id
    ).order_by("order"):
        child = item.child
        click.echo(f"{'  ' * depth}[{item.order}] {type(child).__name__} '{child}'")
        if isinstance(child, CoursePart):
            _outline(child.pk, depth + 1)
        if isinstance(child, Form):
            for page in FormPage._base_manager.filter(form=child).order_by("order"):
                click.echo(f"{'  ' * (depth + 1)}page {page.order}: '{page.title}'")


@click.command()
@click.option("--site-name", default="DemoDev", show_default=True)
def command(site_name: str) -> None:
    """Seed the course structure variants QA scenario."""
    site = Site.objects.get(name=site_name)
    _pin_current_site(site)
    with _site_context(site), transaction.atomic():
        _purge(site)
        org = Organisation._base_manager.get(site=site, slug=DEMODEV_ORG_SLUG)
        cohort = Cohort._base_manager.filter(
            site=site, organisation=org, name=DEMODEV_COHORT
        ).first()
        if cohort is None:
            raise click.ClickException(
                f"Cohort {DEMODEV_COHORT!r} not found; run "
                "`qa_create_course_content_preview` first."
            )
        courses = [_build_multi_page(site), _build_long(site)]
        for course in courses:
            CohortCourseRegistrationFactory(cohort=cohort, course=course, site=site)

    click.secho("\n--- Course structure variants QA ---", fg="cyan", bold=True)
    click.echo(f"Site: {site.name} ({site.domain}); cohort {cohort.name} [{cohort.pk}]")
    for course in courses:
        click.echo(f"Course '{course.title}': pk {course.pk} slug {course.slug}")
        _outline(course.pk)
        click.echo(
            f"URL: /educator/organisations/{DEMODEV_ORG_SLUG}/courses/{course.pk}"
        )
