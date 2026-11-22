"""Seed the browser-QA scenario for the revision page.

Creates (idempotently) on one site (default: DemoDev):

1. "QA Revision Course" with four parts:

   1. "Foundations" (finished): two topics and a completed quiz. Its questions
      carry explanations. One is due now with a low stability, one is
      scheduled 30 days ahead and two have no schedule. One further question
      has ``dropped_from_source_at`` set, so no bank holds it.
   2. "Practice" (finished, weak): six reviews in the log, four of them wrong,
      and three questions due now.
   3. "Advanced" (not finished): questions that must not appear in a bank.
   4. "Backlog" (finished): 45 ready questions spread over twelve topics, one
      topic holding twelve of them, so the "Revision" card reads "40+ ready"
      and that topic reads "10+ ready".

2. Learners (password equals the email address):

   - ``qa-revision@example.com``: the states above.
   - ``qa-revision-new@example.com``: registered, no section finished.
   - ``qa-revision-back@example.com``: the same bank and schedules as the
     first learner, whose last review was 20 days ago.

3. "QA Revision Empty Course": a course whose questions name no section. The
   first learner is registered on it.

Questions live in forms placed in no course (the part 2 to part 4 banks) or in
the part 1 quiz; every question is multiple choice with one correct option.

A re-run creates nothing twice and leaves reviews and schedules already
written alone.

Usage:
    uv run python manage.py qa_create_revision_scenario
    uv run python manage.py qa_create_revision_scenario --site-name DemoDev
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import cast

import djclick as click

from django.contrib.sites.models import Site
from django.utils import timezone

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    CoursePartFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import (
    ContentCollectionItem,
    Course,
    CoursePart,
    Topic,
)
from freedom_ls.content_engine.models.question_sections import (
    FormQuestionCoursePart,
    FormQuestionTopic,
)
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
)
from freedom_ls.form_engine.models import Form, FormQuestion, FormStrategy
from freedom_ls.learner_progress.factories import TopicProgressFactory
from freedom_ls.learner_progress.models import TopicProgress
from freedom_ls.learner_progress.queries import course_progress_for
from freedom_ls.qa_helpers.management.commands.qa_create_multiselect_quiz_scoring import (
    _add_options,
    _complete_quiz_attempt,
    _get_or_create_user,
    _get_site,
    _register,
)
from freedom_ls.revision.factories import (
    RevisionReviewFactory,
    RevisionScheduleFactory,
)
from freedom_ls.revision.models import RevisionReview, RevisionSchedule

COURSE_TITLE = "QA Revision Course"
COURSE_SLUG = "qa-revision-course"
EMPTY_COURSE_TITLE = "QA Revision Empty Course"
EMPTY_COURSE_SLUG = "qa-revision-empty-course"

MAIN_EMAIL = "qa-revision@example.com"
NEW_EMAIL = "qa-revision-new@example.com"
BACK_EMAIL = "qa-revision-back@example.com"

FILE_PATH_ROOT = "qa/revision"
BACKLOG_TOPIC_COUNT = 12
BACKLOG_BIG_TOPIC_QUESTIONS = 12
BACKLOG_OTHER_TOPIC_QUESTIONS = 3
RECENT_REVIEW_DAYS_AGO = 2
BACK_REVIEW_DAYS_AGO = 20
OPTION_TEXTS = ["Option A", "Option B", "Option C"]

Section = Topic | CoursePart


@dataclass(frozen=True)
class QuestionSpec:
    text: str
    sections: tuple[Section, ...]
    explanation: str = ""
    dropped: bool = False


@dataclass
class SeededCourse:
    course: Course
    foundations_questions: list[FormQuestion]
    practice_questions: list[FormQuestion]


def _file_path(*parts: str) -> str:
    """A plausible source-file path for a scenario row; the admin requires one."""
    return "/".join([FILE_PATH_ROOT, *parts])


def _get_or_create_topic(site: Site, slug: str, title: str) -> Topic:
    existing: Topic | None = Topic.objects.filter(slug=slug, site=site).first()
    if existing is not None:
        return existing
    return cast(
        Topic,
        TopicFactory(
            title=title,
            slug=slug,
            file_path=_file_path("topics", f"{slug}.md"),
            site=site,
        ),
    )


def _get_or_create_part(site: Site, slug: str, title: str) -> CoursePart:
    existing: CoursePart | None = CoursePart.objects.filter(
        slug=slug, site=site
    ).first()
    if existing is not None:
        return existing
    return cast(
        CoursePart,
        CoursePartFactory(
            title=title,
            slug=slug,
            file_path=_file_path("parts", f"{slug}.md"),
            site=site,
        ),
    )


def _get_or_create_course(site: Site, slug: str, title: str) -> Course:
    existing: Course | None = Course.objects.filter(slug=slug, site=site).first()
    if existing is not None:
        return existing
    return cast(
        Course,
        CourseFactory(
            title=title,
            slug=slug,
            description="QA course for the revision page.",
            file_path=_file_path("courses", f"{slug}.md"),
            site=site,
        ),
    )


def _place(
    collection: Course | CoursePart,
    child: Topic | CoursePart | Form,
    order: int,
    site: Site,
) -> ContentCollectionItem:
    """The placement of `child` in `collection`, created if it is missing."""
    existing: ContentCollectionItem | None = collection.items.filter(
        child_id=child.pk
    ).first()
    if existing is not None:
        return existing
    return cast(
        ContentCollectionItem,
        ContentCollectionItemFactory(
            collection_object=collection, child_object=child, order=order, site=site
        ),
    )


def _build_form(
    site: Site, slug: str, title: str, specs: list[QuestionSpec]
) -> tuple[Form, list[FormQuestion]]:
    """The form and its questions in order, built from `specs` on the first run."""
    form: Form | None = Form.objects.filter(slug=slug, site=site).first()
    if form is None:
        form = cast(
            Form,
            FormFactory(
                title=title,
                slug=slug,
                strategy=FormStrategy.QUIZ,
                quiz_pass_percentage=50,
                file_path=_file_path("forms", slug, "form.md"),
                site=site,
            ),
        )
        page = FormPageFactory(
            form=form,
            title=f"{title} questions",
            slug=f"{slug}-page-1",
            order=1,
            file_path=_file_path("forms", slug, "page-1.md"),
            site=site,
        )
        for order, spec in enumerate(specs, start=1):
            question = cast(
                FormQuestion,
                FormQuestionFactory(
                    form_page=page,
                    question=spec.text,
                    type="multiple_choice",
                    required=True,
                    explanation=spec.explanation,
                    dropped_from_source_at=timezone.now() if spec.dropped else None,
                    file_path=_file_path("forms", slug, f"question-{order}.md"),
                    order=order,
                    site=site,
                ),
            )
            _add_options(
                question,
                [(text, i == 0) for i, text in enumerate(OPTION_TEXTS)],
                site,
            )
            for section in spec.sections:
                if isinstance(section, Topic):
                    FormQuestionTopic.objects.get_or_create(
                        question=question, topic=section
                    )
                else:
                    FormQuestionCoursePart.objects.get_or_create(
                        question=question, course_part=section
                    )
    questions = list(
        FormQuestion.objects.filter(form_page__form=form).order_by(
            "form_page__order", "order"
        )
    )
    return form, questions


def _complete_topic(
    record_user: User,
    course: Course,
    topic: Topic,
    item: ContentCollectionItem,
    site: Site,
) -> None:
    record = course_progress_for(record_user, course)
    if record is None:
        raise click.ClickException(
            f"No CourseProgress record for {record_user.email} on {course.slug}."
        )
    if not TopicProgress.objects.filter(
        course_progress=record, collection_item=item, complete_time__isnull=False
    ).exists():
        TopicProgressFactory(
            course_progress=record,
            topic=topic,
            collection_item=item,
            complete_time=timezone.now(),
            site=site,
        )


def _seed_memory(
    user: User,
    course: Course,
    foundations: list[FormQuestion],
    practice: list[FormQuestion],
    site: Site,
    *,
    reviews_days_ago: int,
) -> None:
    """Schedules and reviews for one learner. Leaves rows already written alone."""
    now = timezone.now()
    schedules: list[tuple[FormQuestion, timedelta, float]] = [
        (foundations[0], -timedelta(hours=1), 0.5),
        (foundations[1], timedelta(days=30), 40.0),
        (practice[0], -timedelta(days=1), 3.0),
        (practice[1], -timedelta(days=1), 3.0),
        (practice[2], -timedelta(days=1), 3.0),
        (practice[3], timedelta(days=7), 8.0),
        (practice[4], timedelta(days=7), 8.0),
    ]
    for question, due_offset, stability in schedules:
        if not RevisionSchedule.objects.filter(user=user, question=question).exists():
            RevisionScheduleFactory(
                user=user,
                question=question,
                due=now + due_offset,
                stability=stability,
                last_review=now - timedelta(days=reviews_days_ago),
                site=site,
            )

    if RevisionReview.objects.filter(user=user, course=course).exists():
        return
    # Four wrong answers in six reviews: over the weak threshold.
    outcomes: list[tuple[FormQuestion, bool]] = [
        (practice[0], False),
        (practice[1], False),
        (practice[2], False),
        (practice[3], False),
        (practice[4], True),
        (practice[4], True),
    ]
    base: datetime = now - timedelta(days=reviews_days_ago)
    for index, (question, was_correct) in enumerate(outcomes):
        RevisionReviewFactory(
            user=user,
            question=question,
            course=course,
            reviewed_at=base - timedelta(minutes=len(outcomes) - index),
            selected_option_ids=[],
            was_correct=was_correct,
            rating=3 if was_correct else 1,
            site=site,
        )


def _build_course(site: Site) -> SeededCourse:
    course = _get_or_create_course(site, COURSE_SLUG, COURSE_TITLE)

    foundations = _get_or_create_part(site, "qa-revision-foundations", "Foundations")
    practice = _get_or_create_part(site, "qa-revision-practice", "Practice")
    advanced = _get_or_create_part(site, "qa-revision-advanced", "Advanced")
    backlog = _get_or_create_part(site, "qa-revision-backlog", "Backlog")
    for order, part in enumerate([foundations, practice, advanced, backlog]):
        _place(course, part, order, site)

    foundations_topics = [
        _get_or_create_topic(site, "qa-revision-foundations-a", "Foundations A"),
        _get_or_create_topic(site, "qa-revision-foundations-b", "Foundations B"),
    ]
    practice_topic = _get_or_create_topic(site, "qa-revision-practice-a", "Practice A")
    advanced_topic = _get_or_create_topic(site, "qa-revision-advanced-a", "Advanced A")
    backlog_topics = [
        _get_or_create_topic(site, f"qa-revision-backlog-{n}", f"Backlog topic {n}")
        for n in range(1, BACKLOG_TOPIC_COUNT + 1)
    ]
    for order, topic in enumerate(foundations_topics):
        _place(foundations, topic, order, site)
    _place(practice, practice_topic, 0, site)
    _place(advanced, advanced_topic, 0, site)
    for order, topic in enumerate(backlog_topics):
        _place(backlog, topic, order, site)

    quiz, foundations_questions = _build_form(
        site,
        "qa-revision-foundations-quiz",
        "QA Revision Foundations Quiz",
        [
            QuestionSpec(
                f"Foundations question {n}: which option is correct?",
                (foundations,),
                explanation=f"Option A is correct for foundations question {n}.",
                dropped=n == 5,
            )
            for n in range(1, 6)
        ],
    )
    _place(foundations, quiz, len(foundations_topics), site)

    _, practice_questions = _build_form(
        site,
        "qa-revision-practice-bank",
        "QA Revision Practice Bank",
        [
            QuestionSpec(
                f"Practice question {n}: which option is correct?",
                (practice,),
                explanation=f"Option A is correct for practice question {n}.",
            )
            for n in range(1, 6)
        ],
    )
    _build_form(
        site,
        "qa-revision-advanced-bank",
        "QA Revision Advanced Bank",
        [
            QuestionSpec(
                f"Advanced question {n}: which option is correct?", (advanced,)
            )
            for n in range(1, 4)
        ],
    )
    backlog_specs = [
        QuestionSpec(
            f"Backlog question {topic_number}.{n}: which option is correct?", (topic,)
        )
        for topic_number, topic in enumerate(backlog_topics, start=1)
        for n in range(
            1,
            (
                BACKLOG_BIG_TOPIC_QUESTIONS
                if topic_number == 1
                else BACKLOG_OTHER_TOPIC_QUESTIONS
            )
            + 1,
        )
    ]
    _build_form(
        site, "qa-revision-backlog-bank", "QA Revision Backlog Bank", backlog_specs
    )

    return SeededCourse(
        course=Course.objects.get(pk=course.pk),
        foundations_questions=foundations_questions,
        practice_questions=practice_questions,
    )


def _finish_sections(user: User, seeded: SeededCourse, site: Site) -> None:
    """Complete parts 1, 2 and 4 for `user`, leaving part 3 unfinished."""
    course = seeded.course
    finished_slugs = {
        "qa-revision-foundations",
        "qa-revision-practice",
        "qa-revision-backlog",
    }
    for part_item in course.collection_items():
        part = part_item.child
        if not isinstance(part, CoursePart) or part.slug not in finished_slugs:
            continue
        for item in part.collection_items():
            child = item.child
            if isinstance(child, Topic):
                _complete_topic(user, course, child, item, site)
            elif isinstance(child, Form):
                _complete_quiz_attempt(user, course, child, site, answer_correctly=True)


@click.command()
@click.option(
    "--site-name",
    default="DemoDev",
    help="Site name to create the data on (default: 'DemoDev').",
)
def command(site_name: str) -> None:
    """Seed the revision-page browser-QA courses, learners, schedules and reviews."""
    site = _get_site(site_name)

    seeded = _build_course(site)
    empty_course = _get_or_create_course(site, EMPTY_COURSE_SLUG, EMPTY_COURSE_TITLE)
    _place(
        empty_course,
        _get_or_create_topic(site, "qa-revision-empty-a", "Empty course topic"),
        0,
        site,
    )

    main, _ = _get_or_create_user(site, MAIN_EMAIL, "Revision", "Learner")
    new, _ = _get_or_create_user(site, NEW_EMAIL, "Revision", "New")
    back, _ = _get_or_create_user(site, BACK_EMAIL, "Revision", "Back")
    for user in (main, new, back):
        _register(user, seeded.course, site)
    _register(main, empty_course, site)

    for user, days_ago in (
        (main, RECENT_REVIEW_DAYS_AGO),
        (back, BACK_REVIEW_DAYS_AGO),
    ):
        _finish_sections(user, seeded, site)
        _seed_memory(
            user,
            seeded.course,
            seeded.foundations_questions,
            seeded.practice_questions,
            site,
            reviews_days_ago=days_ago,
        )

    click.secho("\n--- Revision QA data ---", fg="cyan", bold=True)
    click.secho(f"Site: {site.name} ({site.domain}) [id {site.pk}]", fg="cyan")
    for label, user in (("main", main), ("new", new), ("back", back)):
        click.secho(f"Learner ({label}): {user.email} / {user.email}", fg="green")
    for course in (seeded.course, empty_course):
        click.secho(
            f"Course '{course.title}'  /courses/{course.slug}/  "
            f"revision /courses/{course.slug}/revision/",
            fg="cyan",
        )
