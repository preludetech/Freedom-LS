"""Seed the browser-QA scenario for retired content: learners whose records point at
content that a content save has since retired.

Needs the demo content loaded (the "Functionality Demo" courses) with some of it
already retired. Creates (idempotently) on one site (default: DemoDev):

1. Cohort "QA Retire Cohort" in organisation ``demodev``.
2. Learners A and B (``qa.retire.a@example.com``, ``qa.retire.b@example.com``;
   password equals the email), both members of the cohort.
3. Active cohort registrations on "Functionality Demo - Course Parts",
   "Functionality Demo - shuffled quiz" and the RETIRED "Functionality Demo - show
   end with Topic". The retired course refuses registrations through the app, so
   the row is written directly with the factory (no ``clean()``).
4. Course Parts progress. Learner A has completed "Welcome", the retired topic
   "What to Expect" and every other live item (topics plus the two forms, sat
   through ``complete()``), so A is at 100%. Learner B has completed "Welcome" only.
5. One completed, scored sitting each of the "Shuffled quiz". Both learners answer
   every question, including the retired "What colour is the sky at midday?":
   learner A answers it "Green" (wrong) and picks the retired option "Jupiter" on
   "Which planet is third from the Sun?"; learner B answers everything correctly.

A new sitting is never served retired rows, and ``complete()`` drops answers its
paper did not serve. So the quiz sittings are sat as they would have been before
the retirement: inside one transaction the form's retired rows are un-retired,
the sitting is completed (served paper, ``asked``, scores and the progress
recalculation all come from the app's own code), and the original ``retired_at``
values are written back before the transaction commits. No other connection ever
sees the rows un-retired.

A re-run creates nothing twice and leaves completed sittings alone.

Usage:
    uv run python manage.py qa_create_retired_content_scenario
    uv run python manage.py qa_create_retired_content_scenario --site-name DemoDev
"""

from dataclasses import dataclass
from datetime import datetime
from typing import cast

import djclick as click

from django.contrib.sites.models import Site
from django.db import transaction
from django.db.models import Model, QuerySet
from django.utils import timezone

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import ContentCollectionItem, Course, Topic
from freedom_ls.form_engine.factories import QuestionAnswerFactory
from freedom_ls.form_engine.models import (
    Form,
    FormPage,
    FormProgress,
    FormQuestion,
    QuestionAnswer,
    QuestionOption,
)
from freedom_ls.learner_management.factories import CohortFactory
from freedom_ls.learner_management.models import Cohort
from freedom_ls.learner_progress.attempts import ensure_attempt, latest_attempt
from freedom_ls.learner_progress.models import CourseProgress, TopicProgress
from freedom_ls.organisations.models import Organisation
from freedom_ls.qa_helpers.management.commands.qa_create_multiselect_quiz_scoring import (
    _add_member,
    _complete_quiz_attempt,
    _get_or_create_user,
    _get_site,
    _record_for,
    _register_cohort,
)

ORGANISATION_SLUG = "demodev"
COHORT_NAME = "QA Retire Cohort"

PARTS_COURSE_SLUG = "functionality-demo-course-parts"
QUIZ_COURSE_SLUG = "functionality-demo-shuffled-quiz"
RETIRED_COURSE_SLUG = "functionality-demo-show-end-with-topic"
QUIZ_TITLE = "Shuffled quiz"

# question text -> option texts chosen instead of the correct ones.
QuizOverrides = dict[str, tuple[str, ...]]


@dataclass(frozen=True)
class LearnerSpec:
    label: str
    email: str
    # Course Parts topics completed by title, retired ones included. None means
    # every live item of the course, plus the topics listed in extra_topics.
    topics: tuple[str, ...] | None
    extra_topics: tuple[str, ...]
    quiz_overrides: QuizOverrides


LEARNERS = [
    LearnerSpec(
        label="A",
        email="qa.retire.a@example.com",
        topics=None,
        extra_topics=("What to Expect",),
        quiz_overrides={
            "What colour is the sky at midday?": ("Green",),
            "Which planet is third from the Sun?": ("Jupiter",),
        },
    ),
    LearnerSpec(
        label="B",
        email="qa.retire.b@example.com",
        topics=("Welcome",),
        extra_topics=(),
        quiz_overrides={},
    ),
]


def _course(slug: str, site: Site) -> Course:
    """The course by slug, retired or not."""
    course: Course | None = Course._base_manager.filter(slug=slug, site=site).first()
    if course is None:
        raise click.ClickException(
            f"Course '{slug}' not found on site '{site.name}'; load the demo content."
        )
    return course


def _placements(collection: Model) -> list[ContentCollectionItem]:
    """Every placement under a course, parts flattened, retired children included."""
    items: list[ContentCollectionItem] = []
    for item in ContentCollectionItem._base_manager.filter(
        collection_id=collection.pk
    ).order_by("order"):
        child = item.child
        if child is None:
            continue
        if getattr(child, "content_type", None) == "COURSE_PART":
            items.extend(_placements(child))
        else:
            items.append(item)
    return items


def _topic_placement(course: Course, title: str) -> ContentCollectionItem:
    for item in _placements(course):
        if isinstance(item.child, Topic) and item.child.title == title:
            return item
    raise click.ClickException(f"No topic '{title}' placed in '{course.slug}'.")


def _complete_topic(record: CourseProgress, item: ContentCollectionItem) -> None:
    """Complete a topic the way the player does: a save that sets complete_time,
    so the post_save receiver recalculates the record's percentage."""
    topic_progress, _created = TopicProgress.objects.get_or_create(
        course_progress=record,
        collection_item=item,
        defaults={"site_id": record.site_id, "topic": item.child},
    )
    if topic_progress.complete_time is None:
        topic_progress.complete_time = timezone.now()
        topic_progress.save()


def _complete_course_parts(
    spec: LearnerSpec, user: User, course: Course, site: Site
) -> None:
    record = _record_for(user, course)
    if spec.topics is not None:
        for title in spec.topics:
            _complete_topic(record, _topic_placement(course, title))
        return
    for item in course.viewable_collection_items():
        child = item.child
        if isinstance(child, Topic):
            _complete_topic(record, item)
        elif isinstance(child, Form):
            _complete_quiz_attempt(user, course, child, site, answer_correctly=True)
    for title in spec.extra_topics:
        _complete_topic(record, _topic_placement(course, title))


def _retired_rows(form: Form) -> list[tuple[QuerySet[Model], datetime]]:
    """The form's retired pages, questions and options, each as a one-row queryset
    and its retired_at, so they can be un-retired and put back exactly."""
    rows: list[tuple[QuerySet[Model], datetime]] = []
    querysets: list[QuerySet[Model]] = [
        cast("QuerySet[Model]", FormPage._base_manager.filter(form=form)),
        cast(
            "QuerySet[Model]",
            FormQuestion._base_manager.filter(form_page__form=form),
        ),
        cast(
            "QuerySet[Model]",
            QuestionOption._base_manager.filter(question__form_page__form=form),
        ),
    ]
    for queryset in querysets:
        for pk, retired_at in queryset.filter(retired_at__isnull=False).values_list(
            "pk", "retired_at"
        ):
            rows.append((queryset.filter(pk=pk), retired_at))
    return rows


def _sit_quiz_before_retirement(
    user: User, course: Course, form: Form, overrides: QuizOverrides, site: Site
) -> FormProgress:
    """A completed sitting of `form` that was served and answered every row the
    form has, retired ones included. Idempotent."""
    record = _record_for(user, course)
    collection_item = next(
        item for item in course.viewable_collection_items() if item.child == form
    )
    existing = latest_attempt(record, collection_item)
    if existing is not None and existing.completed_time is not None:
        return existing

    with transaction.atomic():
        retired = _retired_rows(form)
        for queryset, _retired_at in retired:
            queryset.update(retired_at=None)
        form = Form.objects.get(pk=form.pk)
        sitting = ensure_attempt(record, collection_item)
        questions = FormQuestion._base_manager.filter(form_page__form=form).order_by(
            "form_page__order", "order"
        )
        for question in questions:
            options = list(
                QuestionOption._base_manager.filter(question=question).order_by("order")
            )
            wanted = overrides.get(question.question)
            if wanted is None:
                chosen = [option for option in options if option.correct]
            else:
                chosen = [option for option in options if option.text in wanted]
            if not chosen or (wanted is not None and len(chosen) != len(wanted)):
                raise click.ClickException(
                    f"Could not pick options {wanted} for '{question.question}'."
                )
            answer: QuestionAnswer | None = QuestionAnswer.objects.filter(
                form_progress=sitting, question=question
            ).first()
            if answer is None:
                answer = cast(
                    QuestionAnswer,
                    QuestionAnswerFactory(
                        form_progress=sitting, question=question, site=site
                    ),
                )
            answer.selected_options.set(chosen)
        sitting.form = form
        sitting.complete()
        for queryset, retired_at in retired:
            queryset.update(retired_at=retired_at)
    sitting.refresh_from_db()
    return sitting


def _get_or_create_cohort(site: Site) -> Cohort:
    organisation = Organisation.objects.filter(
        slug=ORGANISATION_SLUG, site=site
    ).first()
    if organisation is None:
        raise click.ClickException(
            f"Organisation '{ORGANISATION_SLUG}' not found on site '{site.name}'."
        )
    existing: Cohort | None = Cohort.objects.filter(name=COHORT_NAME, site=site).first()
    if existing is not None:
        return existing
    return cast(
        Cohort, CohortFactory(name=COHORT_NAME, site=site, organisation=organisation)
    )


@click.command()
@click.option(
    "--site-name",
    default="DemoDev",
    help="Site name to create the data on (default: 'DemoDev').",
)
def command(site_name: str) -> None:
    """Seed learners whose progress and quiz sittings point at retired content."""
    site = _get_site(site_name)
    parts_course = _course(PARTS_COURSE_SLUG, site)
    quiz_course = _course(QUIZ_COURSE_SLUG, site)
    retired_course = _course(RETIRED_COURSE_SLUG, site)
    quiz = next(
        (
            item.child
            for item in quiz_course.viewable_collection_items()
            if isinstance(item.child, Form) and item.child.title == QUIZ_TITLE
        ),
        None,
    )
    if quiz is None:
        raise click.ClickException(f"No form '{QUIZ_TITLE}' in '{quiz_course.slug}'.")

    cohort = _get_or_create_cohort(site)
    for course in (parts_course, quiz_course, retired_course):
        # The factory saves without clean(), so the retired course's refusal
        # does not apply: this models a registration made before retirement.
        _register_cohort(cohort, course, site)

    sittings: list[tuple[LearnerSpec, User, FormProgress]] = []
    for spec in LEARNERS:
        user, _created = _get_or_create_user(site, spec.email, "Retire", spec.label)
        _add_member(user, cohort, site)
        _complete_course_parts(spec, user, parts_course, site)
        sitting = _sit_quiz_before_retirement(
            user, quiz_course, quiz, spec.quiz_overrides, site
        )
        sittings.append((spec, user, sitting))

    click.secho("\n--- Retired content QA data ---", fg="cyan", bold=True)
    click.secho(f"Site: {site.name} ({site.domain}) [id {site.pk}]", fg="cyan")
    click.secho(
        f"Cohort: '{cohort.name}'  pk={cohort.pk}  "
        f"/educator/organisations/{ORGANISATION_SLUG}/cohorts/{cohort.pk}",
        fg="cyan",
    )
    for spec, user, sitting in sittings:
        click.secho(
            f"\nLearner {spec.label}: {user.email} / {user.email}  user pk={user.pk}",
            fg="green",
        )
        for record in CourseProgress._base_manager.filter(
            learner__user=user
        ).select_related("course"):
            click.echo(
                f"  CourseProgress {record.pk}  '{record.course.title}'  "
                f"{record.progress_percentage}%  completed_time={record.completed_time}"
            )
        click.echo(
            f"  Quiz sitting FormProgress pk={sitting.pk}  "
            f"completed={sitting.completed_time}  scores={sitting.scores}  "
            f"answers={sitting.answers.count()}  "
            f"served_paper={'yes' if sitting.served_paper else 'no'}"
        )
