"""Seed the educator course content preview QA scenario (frontend QA §0.3).

Delete-and-recreate by slug, so it can be re-run: every course below, its
parts, topics, forms, uploaded files, registrations and progress rows are
removed first, then rebuilt. Users, organisations and cohorts are reused.

Builds on the site (default DemoDev):

- "QA Preview Course" (published, priced, category, difficulty, duration,
  time limit, two learning outcomes, About markdown) with the outline
  Welcome / Reading / Part "Module one" (Inside the part, Module quiz) /
  Part "Empty module" / Feedback survey. Welcome holds a picture (a real
  uploaded PNG), a file download, a flashcard, a 10-column table and a code
  block with a 200-character line. Reading holds a content-link to Welcome.
- "QA Empty Course" (published, no items).
- "QA Draft Outline" (the preview course's shape, own copies of every child,
  ``table_of_contents_in_development=True``, published).
- "QA Other Org Course" (published, one topic), an organisation course of
  "QA Other Org" only, registered to a cohort there and nowhere in demodev.
- Cohort "QA Preview Cohort" in demodev, registered for the first three.
- Learner qa-learner@example.com / testpass123 in that cohort.
- Educator qa-other-educator@example.com / testpass123, organisation_admin
  of "QA Other Org" only (via qa_create_single_org_educator).
- Learner qa-other-learner@example.com / testpass123 in "QA Other Org Cohort".

Usage:
    uv run python manage.py qa_create_course_content_preview [--site-name DemoDev]
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from typing import cast

import djclick as click
from allauth.account.models import EmailAddress
from PIL import Image, ImageDraw

from django.contrib.sites.models import Site
from django.core.management import call_command
from django.db import transaction

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseCategoryFactory,
    CourseFactory,
    CoursePartFactory,
    FileFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import (
    ContentCollectionItem,
    Course,
    CourseAudience,
    CourseCategory,
    CoursePart,
    CourseVisibility,
    DifficultyLevel,
    File,
    PriceKind,
    Topic,
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
    FormProgress,
    FormQuestion,
    FormStrategy,
    QuestionOption,
    QuestionType,
)
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    CohortMembership,
    Learner,
    LearnerCourseRegistration,
)
from freedom_ls.learner_progress.models import CourseProgress, TopicProgress
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.qa_helpers.management.commands.qa_create_organisation_scenarios import (
    _pin_current_site,
    _site_context,
)
from freedom_ls.qa_helpers.management.commands.qa_create_single_org_educator import (
    _ensure_consents,
)

PASSWORD = "testpass123"  # noqa: S105  # pragma: allowlist secret  # dev-only QA credential
DEMODEV_ORG_SLUG = "demodev"
DEMODEV_COHORT = "QA Preview Cohort"
OTHER_ORG_NAME = "QA Other Org"
OTHER_ORG_SLUG = "qa-other-org"
OTHER_ORG_COHORT = "QA Other Org Cohort"
LEARNER_EMAIL = "qa-learner@example.com"
OTHER_EDUCATOR_EMAIL = "qa-other-educator@example.com"
OTHER_LEARNER_EMAIL = "qa-other-learner@example.com"
CATEGORY_SLUG = "qa-preview-category"

PREVIEW_SLUG = "qa-preview-course"
EMPTY_SLUG = "qa-empty-course"
DRAFT_SLUG = "qa-draft-outline"
OTHER_SLUG = "qa-other-org-course"
ALL_SLUGS = (PREVIEW_SLUG, EMPTY_SLUG, DRAFT_SLUG, OTHER_SLUG)

PICTURE_NAME = "qa-preview-picture.png"
HANDOUT_NAME = "qa-preview-handout.pdf"

CODE_LINE = (
    "2026-11-10T09:15:42Z INFO request_id=7f3a9c21 path=/educator/organisations/"
    "demodev/courses/preview status=200 duration_ms=184 user=demodev@email.com "
    "note=this-line-is-deliberately-long-so-it-must-scroll"
)
CODE_LINE = (CODE_LINE + "-" * 200)[:200]


@dataclass
class Built:
    """Pks of what one outline build created, keyed by child title."""

    items: dict[str, ContentCollectionItem] = field(default_factory=dict)


# --------------------------------------------------------------------------
# Teardown
# --------------------------------------------------------------------------


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
        click.echo(f"  Course: {course.delete()}")

    prefixes = [f"{slug}-" for slug in ALL_SLUGS]
    for prefix in prefixes:
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
            FormPage._base_manager.filter(form=form).update(condition_option=None)
            click.echo(
                f"  Form {form.pk} '{form}': progress {progress}, {form.delete()}"
            )
    for f in File._base_manager.filter(
        site=site, file_path__startswith="qa-preview-files/"
    ):
        f.file.delete(save=False)
        click.echo(f"  File {f.pk} '{f}': {f.delete()}")


# --------------------------------------------------------------------------
# Users, organisations, cohorts
# --------------------------------------------------------------------------


def _ensure_user(site: Site, email: str, first: str, last: str) -> User:
    user: User | None = User.objects.filter(email=email).first()
    if user is None:
        user = cast(
            User,
            UserFactory(
                email=email,
                first_name=first,
                last_name=last,
                password=PASSWORD,
                site=site,
            ),
        )
    else:
        user.is_active = True
        user.set_password(PASSWORD)
        user.save(update_fields=["is_active", "password"])
    EmailAddress.objects.update_or_create(
        user=user, email=email, defaults={"verified": True, "primary": True}
    )
    _ensure_consents(site, user)
    return user


def _ensure_other_org(site: Site) -> Organisation:
    org = Organisation._base_manager.filter(site=site, slug=OTHER_ORG_SLUG).first()
    if org is None:
        org = cast(
            Organisation,
            OrganisationFactory(name=OTHER_ORG_NAME, slug=OTHER_ORG_SLUG, site=site),
        )
    return org


def _ensure_cohort(site: Site, org: Organisation, name: str) -> Cohort:
    cohort = Cohort._base_manager.filter(site=site, organisation=org, name=name).first()
    if cohort is None:
        cohort = cast(Cohort, CohortFactory(organisation=org, name=name, site=site))
    elif not cohort.is_active:
        cohort.is_active = True
        cohort.save(update_fields=["is_active"])
    return cohort


def _ensure_member(site: Site, cohort: Cohort, user: User) -> None:
    learner = cast(
        Learner, LearnerFactory(user=user, organisation=cohort.organisation, site=site)
    )
    if not CohortMembership._base_manager.filter(
        cohort=cohort, learner=learner
    ).exists():
        CohortMembershipFactory(cohort=cohort, learner=learner, site=site)


# --------------------------------------------------------------------------
# Content
# --------------------------------------------------------------------------


def _png_bytes() -> bytes:
    image = Image.new("RGB", (1200, 700), (30, 64, 120))
    draw = ImageDraw.Draw(image)
    draw.rectangle((80, 80, 1120, 620), outline=(250, 200, 60), width=12)
    draw.ellipse((420, 170, 780, 530), fill=(250, 200, 60))
    draw.text((100, 100), "QA Preview Course picture", fill=(255, 255, 255))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _pdf_bytes() -> bytes:
    return (
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 144]/Contents 4 0 R"
        b"/Resources<</Font<</F1 5 0 R>>>>>>endobj\n"
        b"4 0 obj<</Length 52>>stream\nBT /F1 18 Tf 20 70 Td (QA preview handout) Tj ET\n"
        b"endstream endobj\n5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
        b"trailer<</Root 1 0 R>>\n%%EOF\n"
    )


def _ensure_files(site: Site) -> None:
    FileFactory(
        file_path=f"qa-preview-files/{PICTURE_NAME}",
        original_filename=PICTURE_NAME,
        mime_type="image/png",
        file_type=File.FileType.IMAGE,
        file__data=_png_bytes(),
        file__filename=PICTURE_NAME,
        site=site,
    )
    FileFactory(
        file_path=f"qa-preview-files/{HANDOUT_NAME}",
        original_filename=HANDOUT_NAME,
        mime_type="application/pdf",
        file_type=File.FileType.DOCUMENT,
        file__data=_pdf_bytes(),
        file__filename=HANDOUT_NAME,
        site=site,
    )


def _welcome_markdown() -> str:
    headers = [f"Column {n}" for n in range(1, 11)]
    rows = [
        [f"Row {r} value {c} with some extra words" for c in range(1, 11)]
        for r in range(1, 4)
    ]
    table = "\n".join(
        [
            "| " + " | ".join(headers) + " |",
            "|" + "---|" * len(headers),
            *("| " + " | ".join(row) + " |" for row in rows),
        ]
    )
    return f"""Welcome to the QA preview course. This topic exercises every widget the preview has to render.

<c-picture src="../qa-preview-files/{PICTURE_NAME}" alt="A gold circle inside a gold frame on a dark blue background" title="The QA preview picture" description="Click the picture to open it in the lightbox."></c-picture>

<c-file-download src="../qa-preview-files/{HANDOUT_NAME}" text="Download the course handout"></c-file-download>

<c-flashcard>
<c-slot name="front">

**What does the educator preview show?**

</c-slot>
<c-slot name="back">

Exactly what a learner sees, with nothing saved.

</c-slot>
</c-flashcard>

<c-table caption="A ten-column table that must scroll horizontally">

{table}

</c-table>

<c-code-block title="long-line.log" language="text">short line before
{CODE_LINE}
short line after</c-code-block>
"""


def _topic(site: Site, prefix: str, key: str, title: str, content: str) -> Topic:
    return cast(
        Topic,
        TopicFactory(
            title=title,
            slug=f"{prefix}-{key}",
            file_path=f"{prefix}/{key}.md",
            content=content,
            site=site,
        ),
    )


def _place(
    site: Site, collection: Course | CoursePart, child: object, order: int
) -> ContentCollectionItem:
    return cast(
        ContentCollectionItem,
        ContentCollectionItemFactory(
            collection_object=collection, child_object=child, order=order, site=site
        ),
    )


def _options(
    site: Site, question: FormQuestion, options: list[tuple[str, bool | None]]
) -> list[QuestionOption]:
    return [
        cast(
            QuestionOption,
            QuestionOptionFactory(
                question=question,
                text=text,
                value=text.lower().replace(" ", "_"),
                order=i,
                correct=correct,
                site=site,
            ),
        )
        for i, (text, correct) in enumerate(options)
    ]


def _question(
    site: Site, page: FormPage, text: str, qtype: str, order: int
) -> FormQuestion:
    return cast(
        FormQuestion,
        FormQuestionFactory(
            form_page=page,
            question=text,
            type=qtype,
            order=order,
            required=True,
            site=site,
        ),
    )


def _quiz(site: Site, prefix: str) -> Form:
    form = cast(
        Form,
        FormFactory(
            title="Module quiz",
            slug=f"{prefix}-module-quiz",
            file_path=f"{prefix}/module_one/quiz.md",
            strategy=FormStrategy.QUIZ,
            quiz_pass_percentage=50,
            quiz_show_incorrect=True,
            content="Answer the four questions below.",
            site=site,
        ),
    )
    page = cast(
        FormPage,
        FormPageFactory(
            form=form,
            title="Quiz questions",
            slug=f"{prefix}-module-quiz-p1",
            order=0,
            site=site,
        ),
    )
    mc = _question(
        site,
        page,
        "Which planet is closest to the sun?",
        QuestionType.MULTIPLE_CHOICE,
        0,
    )
    _options(site, mc, [("Venus", False), ("Mercury", True), ("Mars", False)])
    cb = _question(
        site, page, "Which of these are prime numbers?", QuestionType.CHECKBOXES, 1
    )
    _options(
        site, cb, [("Two", True), ("Four", False), ("Seven", True), ("Nine", False)]
    )
    dd = _question(
        site,
        page,
        "Which colour do you get by mixing blue and yellow?",
        QuestionType.DROPDOWN,
        2,
    )
    _options(site, dd, [("Purple", False), ("Green", True), ("Orange", False)])
    _question(site, page, "Name one ocean.", QuestionType.SHORT_TEXT, 3)
    return form


def _survey(site: Site, prefix: str) -> Form:
    form = cast(
        Form,
        FormFactory(
            title="Feedback survey",
            slug=f"{prefix}-feedback-survey",
            file_path=f"{prefix}/survey.md",
            strategy=FormStrategy.UNSCORED,
            quiz_show_incorrect=None,
            quiz_pass_percentage=None,
            content="Tell us how the course went.",
            site=site,
        ),
    )
    page1 = cast(
        FormPage,
        FormPageFactory(
            form=form,
            title="Your feedback",
            slug=f"{prefix}-feedback-survey-p1",
            order=0,
            site=site,
        ),
    )
    enjoy = _question(site, page1, "Did you enjoy it?", QuestionType.MULTIPLE_CHOICE, 0)
    enjoy.slug = "enjoyed"
    enjoy.save(update_fields=["slug"])
    _yes, no = _options(site, enjoy, [("Yes", None), ("No", None)])
    _question(
        site,
        page1,
        "How many hours did you spend on the course?",
        QuestionType.NUMBER,
        1,
    )
    _question(site, page1, "When did you finish?", QuestionType.DATE, 2)
    _question(site, page1, "What would you change?", QuestionType.LONG_TEXT, 3)
    upload = _question(site, page1, "Upload your notes", QuestionType.FILE_UPLOAD, 4)
    upload.required = False
    upload.save(update_fields=["required"])
    page2 = cast(
        FormPage,
        FormPageFactory(
            form=form,
            title="Tell us more",
            slug=f"{prefix}-feedback-survey-p2",
            order=1,
            site=site,
        ),
    )
    page2.condition_option = no
    page2.save(update_fields=["condition_option"])
    _question(site, page2, "What did you not enjoy?", QuestionType.LONG_TEXT, 0)
    return form


def _build_outline(site: Site, course: Course) -> Built:
    prefix = course.slug
    built = Built()
    welcome = _topic(site, prefix, "01_welcome", "Welcome", _welcome_markdown())
    reading = _topic(
        site,
        prefix,
        "02_reading",
        "Reading",
        "Some reading for the course.\n\n"
        'Go back to <c-content-link path="01_welcome.md">the Welcome topic</c-content-link>.\n',
    )
    built.items["Welcome"] = _place(site, course, welcome, 0)
    built.items["Reading"] = _place(site, course, reading, 1)

    module_one = cast(
        CoursePart,
        CoursePartFactory(
            title="Module one",
            slug=f"{prefix}-module-one",
            file_path=f"{prefix}/module_one",
            site=site,
        ),
    )
    built.items["Module one"] = _place(site, course, module_one, 2)
    inside = cast(
        Topic,
        TopicFactory(
            title="Inside the part",
            slug=f"{prefix}-inside-the-part",
            file_path=f"{prefix}/module_one/01_inside.md",
            content="This topic lives **inside** Module one.",
            site=site,
        ),
    )
    built.items["Inside the part"] = _place(site, module_one, inside, 0)
    built.items["Module quiz"] = _place(site, module_one, _quiz(site, prefix), 1)

    empty = cast(
        CoursePart,
        CoursePartFactory(
            title="Empty module",
            slug=f"{prefix}-empty-module",
            file_path=f"{prefix}/empty_module",
            site=site,
        ),
    )
    built.items["Empty module"] = _place(site, course, empty, 3)
    built.items["Feedback survey"] = _place(site, course, _survey(site, prefix), 4)
    return built


def _course(site: Site, title: str, slug: str, **fields: object) -> Course:
    return cast(
        Course,
        CourseFactory(
            title=title,
            slug=slug,
            file_path=f"{slug}/course.md",
            visibility=CourseVisibility.PUBLISHED,
            site=site,
            **fields,
        ),
    )


def _rich_fields(category: CourseCategory) -> dict[str, object]:
    return {
        "subtitle": "Checking the content preview",
        "description": "A course built to check the educator content preview.",
        "content": (
            "This course exists so educators can check **every** preview.\n\n"
            "It covers topics, parts, a quiz and a survey."
        ),
        "dashboard_category": category,
        "difficulty": DifficultyLevel.INTERMEDIATE,
        "estimated_duration": timedelta(hours=1, minutes=30),
        "time_limit_days": 90,
        "learning_outcomes": [
            "Read a course outline in the educator interface",
            "Preview a topic, a quiz and a survey without saving anything",
        ],
    }


@click.command()
@click.option("--site-name", default="DemoDev", show_default=True)
def command(site_name: str) -> None:
    """Seed the course content preview QA scenario."""
    site = Site.objects.get(name=site_name)
    _pin_current_site(site)
    with _site_context(site), transaction.atomic():
        _purge(site)

        demodev = Organisation._base_manager.get(site=site, slug=DEMODEV_ORG_SLUG)
        other_org = _ensure_other_org(site)
        demodev_cohort = _ensure_cohort(site, demodev, DEMODEV_COHORT)
        other_cohort = _ensure_cohort(site, other_org, OTHER_ORG_COHORT)

        category = CourseCategory._base_manager.filter(
            site=site, slug=CATEGORY_SLUG
        ).first()
        if category is None:
            category = cast(
                CourseCategory,
                CourseCategoryFactory(
                    title="QA Preview Category", slug=CATEGORY_SLUG, site=site
                ),
            )

        _ensure_files(site)

        preview = _course(
            site,
            "QA Preview Course",
            PREVIEW_SLUG,
            price_kind=PriceKind.FIXED,
            price_amount=Decimal("49.00"),
            price_currency="USD",
            **_rich_fields(category),
        )
        preview.categories.add(category)
        preview_built = _build_outline(site, preview)

        empty = _course(site, "QA Empty Course", EMPTY_SLUG)

        draft = _course(
            site,
            "QA Draft Outline",
            DRAFT_SLUG,
            table_of_contents_in_development=True,
            **_rich_fields(category),
        )
        draft.categories.add(category)
        draft_built = _build_outline(site, draft)

        other = _course(
            site,
            "QA Other Org Course",
            OTHER_SLUG,
            subtitle="Belongs to QA Other Org only",
            audience=CourseAudience.ORGANISATION_LEARNERS,
        )
        other.organisations.set([other_org])
        other_topic = _topic(
            site,
            OTHER_SLUG,
            "01_other_topic",
            "Other org topic",
            "Only QA Other Org sees this.",
        )
        other_item = _place(site, other, other_topic, 0)

        for course in (preview, empty, draft):
            CohortCourseRegistrationFactory(
                cohort=demodev_cohort, course=course, site=site
            )
        CohortCourseRegistrationFactory(cohort=other_cohort, course=other, site=site)

        learner = _ensure_user(site, LEARNER_EMAIL, "Quill", "Learner")
        _ensure_member(site, demodev_cohort, learner)
        other_learner = _ensure_user(site, OTHER_LEARNER_EMAIL, "Otto", "Learner")
        _ensure_member(site, other_cohort, other_learner)

    call_command(
        "qa_create_single_org_educator",
        "--site",
        site_name,
        "--organisation-slug",
        OTHER_ORG_SLUG,
        "--email",
        OTHER_EDUCATOR_EMAIL,
        "--first-name",
        "Olu",
        "--last-name",
        "Educator",
        "--password",
        PASSWORD,
    )

    click.secho("\n--- Course content preview QA ---", fg="cyan", bold=True)
    click.echo(f"Site: {site.name} ({site.domain}) [id {site.pk}]")
    click.echo(
        f"Organisations: {demodev.slug} [{demodev.pk}], {other_org.slug} [{other_org.pk}]"
    )
    click.echo(
        f"Cohorts: {demodev_cohort.name} [{demodev_cohort.pk}], {other_cohort.name} [{other_cohort.pk}]"
    )
    for course in (preview, empty, draft, other):
        click.echo(f"Course '{course.title}': pk {course.pk} slug {course.slug}")
    for label, built in (("Preview", preview_built), ("Draft", draft_built)):
        for title, item in built.items.items():
            click.echo(f"  {label} item '{title}': {item.pk}")
    click.echo(f"  Other org item 'Other org topic': {other_item.pk}")
    for course in (preview, empty, draft):
        click.echo(
            f"URL: /educator/organisations/{DEMODEV_ORG_SLUG}/courses/{course.pk}"
        )
    click.echo(
        f"Users (password {PASSWORD}): {LEARNER_EMAIL}, {OTHER_EDUCATOR_EMAIL}, {OTHER_LEARNER_EMAIL}"
    )
