"""Batched, site-explicit loading of everything the cohort report reads from the ORM.

This is the only module in the report pipeline that queries. Each loader below
issues its queries once and returns one frozen bundle; `freedom_ls.reports.gather`
assembles those bundles into the report tree without touching the database again.

Runs from a background task, which has no HTTP request, so
`SiteAwareManager.get_queryset()` cannot filter by site on its own — every query
here filters explicitly on `site_id=site_id`.

`frozen=True` on the bundles freezes the binding, not the maps inside them.
Nothing downstream of a loader may mutate what it returns: the course sections
and the student details are built from the same bundles, so a mutation in one
would be visible to the other.
"""

from __future__ import annotations

import dataclasses
from collections import defaultdict
from datetime import datetime
from typing import TypedDict, cast
from uuid import UUID

from django.contrib.sites.models import Site
from django.db.models import Count, F, Window
from django.db.models.functions import RowNumber

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import (
    FREE_TEXT_QUESTION_TYPES,
    Form,
    FormQuestion,
    FormStrategy,
    QuestionOption,
    Topic,
)
from freedom_ls.reports.config import config
from freedom_ls.reports.report_data import ReportTooLargeError
from freedom_ls.site_aware_models.config import config as site_config
from freedom_ls.student_management.models import (
    Cohort,
    CohortCourseRegistration,
    CohortMembership,
)
from freedom_ls.student_progress.models import (
    FormProgress,
    QuestionAnswer,
    TopicProgress,
)
from freedom_ls.student_progress.queries import attempt_completes_form
from freedom_ls.student_progress.scoring import evaluate_quiz_answers


@dataclasses.dataclass(frozen=True)
class CohortRoster:
    """The cohort's members, in the one order the whole report uses."""

    students_by_id: dict[int, User]
    sort_key_by_id: dict[int, tuple[str, str]]
    student_ids: list[int]


@dataclasses.dataclass(frozen=True)
class CourseCatalogue:
    """Every viewable item in the cohort's courses, indexed for lookup."""

    course_items: dict[UUID, list[Topic | Form]]
    # Every course's items concatenated, in registration order. An item shared
    # by two courses appears twice, and so counts twice in a student's overall
    # denominator -- the per-course figures are the ones that never double up.
    all_items: list[Topic | Form]
    forms_by_id: dict[UUID, Form]
    topic_ids: set[UUID]
    form_ids: set[UUID]
    quiz_form_ids: set[UUID]
    # The order quizzes appear in their courses, which is the order the summary
    # table columns and a student's wrong-answer blocks both follow.
    # Deduplicated across courses, unlike all_items.
    ordered_quiz_form_ids: list[UUID]


@dataclasses.dataclass(frozen=True)
class TopicProgressIndex:
    user_ids_seen: set[int]
    completed_topic_ids_by_user: dict[int, set[UUID]]
    complete_time: dict[tuple[int, UUID], datetime]


@dataclasses.dataclass(frozen=True)
class FormProgressIndex:
    """Every form sitting the cohort has, keyed for the per-student lookups.

    Built from one queryset ordered completed-time-descending, nulls last. That
    ordering is load-bearing twice: it decides which row is `latest_by_user_form`
    for a pair, and it is the order `completed_attempts_by_user_form` is reversed
    out of. Neither can be re-derived from this bundle, so both are settled at
    construction and nothing here may be re-sorted afterwards.
    """

    user_ids_seen: set[int]
    # First row seen per pair, which the ordering above makes the latest
    # completed sitting where one exists and the latest started sitting
    # otherwise. `_completed_items` relies on this to know completed_time is set.
    latest_by_user_form: dict[tuple[int, UUID], FormProgress]
    # Every completed sitting, not merely how many there were: the per-student
    # attempts table reads from this, and a count would only have to be
    # reconciled against it later. Chronological, oldest first.
    completed_attempts_by_user_form: dict[tuple[int, UUID], list[FormProgress]]
    completed_form_ids_by_user: dict[int, set[UUID]]
    # Newest-completed first, NOT the chronological order of the lists above.
    # It is the outer loop of the sat pairs, and so the order each WrongAnswer's
    # selected options are first seen in -- reordering it reorders those.
    completed_attempt_ids: list[UUID]
    # Every form progress row, quiz or not: a completed survey sitting is in
    # completed_attempt_ids and must resolve here without a KeyError.
    user_form_by_attempt_id: dict[UUID, tuple[int, UUID]]


@dataclasses.dataclass(frozen=True)
class ProgressIndex:
    topics: TopicProgressIndex
    forms: FormProgressIndex
    # Union of the two sources: a student counts as started the moment either a
    # TopicProgress or a FormProgress row exists for them, complete or not.
    # A field rather than a property, so the per-student membership test stays
    # O(1) instead of rebuilding the union once per student.
    user_ids_with_any_progress: set[int]


@dataclasses.dataclass(frozen=True)
class QuestionIndex:
    """Every quiz question in the cohort's courses, numbered and with its options."""

    question_ids: list[UUID]
    by_id: dict[UUID, FormQuestion]
    by_form: dict[UUID, list[FormQuestion]]
    options_by_question: dict[UUID, list[QuestionOption]]
    correct_option_texts: dict[UUID, list[str]]
    number_by_id: dict[UUID, int]


@dataclasses.dataclass(frozen=True)
class SatQuestions:
    """Every (completed sitting, scorable question) pair, and how it was answered."""

    pairs: list[tuple[UUID, FormQuestion]]
    selected_options_by_pair: dict[tuple[UUID, UUID], list[QuestionOption]]
    correctness: dict[tuple[UUID, UUID], bool]


def _student_sort_key(user: User) -> tuple[str, str]:
    """Surname-first ordering, falling back to the email when no surname is set."""
    first_name = (user.first_name or "").strip()
    last_name = (user.last_name or "").strip()
    return (last_name or user.email, first_name)


def load_cohort(cohort_id: str, site_id: int) -> Cohort:
    # Bound to a typed local first: the site-aware manager is untyped, so its
    # .get() is Any, and returning that directly trips warn_return_any.
    cohort: Cohort = Cohort.objects.get(pk=cohort_id, site_id=site_id)
    return cohort


def load_registrations(cohort: Cohort, site_id: int) -> list[CohortCourseRegistration]:
    # select_related("collection") feeds the course title and id on every
    # section; without it each registration would re-query for its course.
    return list(
        CohortCourseRegistration.objects.filter(cohort=cohort, site_id=site_id)
        .select_related("collection")
        .order_by("-is_active", "collection__title")
    )


def load_roster(cohort: Cohort, site_id: int) -> CohortRoster:
    """The cohort's members in report order, refusing a cohort too large to render."""
    memberships = list(
        CohortMembership.objects.filter(cohort=cohort, site_id=site_id).select_related(
            "user"
        )
    )
    students_by_id: dict[int, User] = {m.user_id: m.user for m in memberships}
    # One ordering, computed once, used for the summary tables and the
    # per-student sections alike -- cohort membership query order would put the
    # summary table out of step with the Contents page and the student
    # sections, which are both alphabetical by surname.
    sort_key_by_id: dict[int, tuple[str, str]] = {
        user_id: _student_sort_key(user) for user_id, user in students_by_id.items()
    }
    student_ids = sorted(students_by_id, key=lambda user_id: sort_key_by_id[user_id])

    if len(student_ids) > config.REPORTS_MAX_STUDENTS:
        raise ReportTooLargeError(
            f"Cohort '{cohort.name}' has {len(student_ids)} students, exceeding "
            f"the configured limit of {config.REPORTS_MAX_STUDENTS} "
            "(REPORTS_MAX_STUDENTS)."
        )

    return CohortRoster(
        students_by_id=students_by_id,
        sort_key_by_id=sort_key_by_id,
        student_ids=student_ids,
    )


def build_course_catalogue(
    registrations: list[CohortCourseRegistration],
) -> CourseCatalogue:
    """Every viewable item in the cohort's courses, indexed for the loaders below.

    Course items are gathered per course (one children() traversal each,
    memoized on the instance) — bounded by course/CoursePart structure, not
    by student or question counts. viewable_items() only excludes CoursePart
    sentinels, so Activities are filtered out here, taking them out of the
    completion denominator too (no ActivityProgress model exists).
    """
    course_items: dict[UUID, list[Topic | Form]] = {}
    forms_by_id: dict[UUID, Form] = {}
    topic_ids: set[UUID] = set()
    form_ids: set[UUID] = set()
    quiz_form_ids: set[UUID] = set()
    ordered_quiz_form_ids: list[UUID] = []
    for reg in registrations:
        items = [
            item
            for item in reg.collection.viewable_items()
            if isinstance(item, Topic | Form)
        ]
        course_items[reg.collection_id] = items
        for item in items:
            if isinstance(item, Topic):
                topic_ids.add(item.id)
            else:
                form_ids.add(item.id)
                forms_by_id[item.id] = item
                if item.strategy == FormStrategy.QUIZ and item.id not in quiz_form_ids:
                    quiz_form_ids.add(item.id)
                    ordered_quiz_form_ids.append(item.id)

    return CourseCatalogue(
        course_items=course_items,
        all_items=[item for items in course_items.values() for item in items],
        forms_by_id=forms_by_id,
        topic_ids=topic_ids,
        form_ids=form_ids,
        quiz_form_ids=quiz_form_ids,
        ordered_quiz_form_ids=ordered_quiz_form_ids,
    )


def load_topic_progress_rows(
    site_id: int, student_ids: list[int], topic_ids: set[UUID]
) -> list[tuple[int, UUID, datetime | None]]:
    """(user_id, topic_id, complete_time) for the cohort's topics, in one query."""
    return list(
        TopicProgress.objects.filter(
            site_id=site_id, user_id__in=student_ids, topic_id__in=topic_ids
        ).values_list("user_id", "topic_id", "complete_time")
    )


def fold_topic_progress_rows(
    rows: list[tuple[int, UUID, datetime | None]],
) -> TopicProgressIndex:
    """Index the loaded topic rows. A row with no complete_time still counts as activity."""
    user_ids_seen: set[int] = set()
    completed_topic_ids_by_user: dict[int, set[UUID]] = defaultdict(set)
    complete_time: dict[tuple[int, UUID], datetime] = {}
    for user_id, topic_id, topic_complete_time in rows:
        user_ids_seen.add(user_id)
        if topic_complete_time is not None:
            completed_topic_ids_by_user[user_id].add(topic_id)
            complete_time[(user_id, topic_id)] = topic_complete_time

    return TopicProgressIndex(
        user_ids_seen=user_ids_seen,
        completed_topic_ids_by_user=completed_topic_ids_by_user,
        complete_time=complete_time,
    )


def load_form_progress_rows(
    site_id: int, student_ids: list[int], form_ids: set[UUID]
) -> list[FormProgress]:
    """Every sitting of the cohort's forms, newest-completed first, in one query.

    The ordering is the contract `fold_form_progress_rows` is written against.
    select_related("form") feeds attempt_completes_form(), which reads
    attempt.form; without it that is one extra query per completed attempt.
    """
    return list(
        FormProgress.objects.filter(
            site_id=site_id, user_id__in=student_ids, form_id__in=form_ids
        )
        .select_related("form")
        .order_by(F("completed_time").desc(nulls_last=True), "-start_time")
    )


def fold_form_progress_rows(
    form_progress_rows: list[FormProgress],
) -> FormProgressIndex:
    """Index the loaded sittings, which must arrive newest-completed first."""
    user_ids_seen: set[int] = set()
    latest_by_user_form: dict[tuple[int, UUID], FormProgress] = {}
    completed_attempts_by_user_form: dict[tuple[int, UUID], list[FormProgress]] = (
        defaultdict(list)
    )
    completed_form_ids_by_user: dict[int, set[UUID]] = defaultdict(set)
    completed_attempt_ids: list[UUID] = []
    user_form_by_attempt_id: dict[UUID, tuple[int, UUID]] = {}
    for fp in form_progress_rows:
        user_ids_seen.add(fp.user_id)
        key = (fp.user_id, fp.form_id)
        user_form_by_attempt_id[fp.id] = key
        if key not in latest_by_user_form:
            latest_by_user_form[key] = fp
        if fp.completed_time is not None:
            # Rows arrive newest-completed first, so the first completed sitting
            # seen for a key is the learner's latest — the one whose verdict
            # decides whether they are done with the form. Read before the
            # append: the list is a defaultdict, so appending first would make
            # every sitting look like the latest.
            is_latest_completed = key not in completed_attempts_by_user_form
            completed_attempts_by_user_form[key].append(fp)
            if is_latest_completed and attempt_completes_form(fp):
                completed_form_ids_by_user[fp.user_id].add(fp.form_id)
            completed_attempt_ids.append(fp.id)

    # The rows arrive newest-completed first; a reader of a student's section
    # wants their sittings in the order they sat them. completed_attempt_ids is
    # deliberately left newest-first -- see its field comment.
    for attempt_rows in completed_attempts_by_user_form.values():
        attempt_rows.reverse()

    return FormProgressIndex(
        user_ids_seen=user_ids_seen,
        latest_by_user_form=latest_by_user_form,
        completed_attempts_by_user_form=completed_attempts_by_user_form,
        completed_form_ids_by_user=completed_form_ids_by_user,
        completed_attempt_ids=completed_attempt_ids,
        user_form_by_attempt_id=user_form_by_attempt_id,
    )


def merge_progress_indexes(
    topics: TopicProgressIndex, forms: FormProgressIndex
) -> ProgressIndex:
    return ProgressIndex(
        topics=topics,
        forms=forms,
        user_ids_with_any_progress=topics.user_ids_seen | forms.user_ids_seen,
    )


def load_progress_index(
    site_id: int, student_ids: list[int], catalogue: CourseCatalogue
) -> ProgressIndex:
    """Both progress sources, loaded and merged.

    The two are merged rather than sharing one accumulator so neither builder
    depends on the other having run first.
    """
    return merge_progress_indexes(
        fold_topic_progress_rows(
            load_topic_progress_rows(site_id, student_ids, catalogue.topic_ids)
        ),
        fold_form_progress_rows(
            load_form_progress_rows(site_id, student_ids, catalogue.form_ids)
        ),
    )


def load_first_attempt_ids(
    site_id: int, student_ids: list[int], quiz_form_ids: set[UUID]
) -> set[UUID]:
    """The id of each student's earliest completed sitting of each quiz."""
    # Filtering directly on a window annotation works from Django 4.2 onward.
    return set(
        FormProgress.objects.filter(
            site_id=site_id,
            user_id__in=student_ids,
            form_id__in=quiz_form_ids,
            completed_time__isnull=False,
        )
        .annotate(
            rank=Window(
                RowNumber(),
                partition_by=[F("user_id"), F("form_id")],
                order_by=F("start_time").asc(),
            )
        )
        .filter(rank=1)
        .values_list("id", flat=True)
    )


def load_quiz_questions(
    site_id: int, quiz_form_ids: set[UUID]
) -> tuple[list[FormQuestion], dict[UUID, list[QuestionOption]]]:
    """Every quiz question in page-then-position order, with its options.

    DO NOT call FormQuestion.question_number() (re-queries per call) or
    FormPage.children() (not prefetch-friendly) -- question numbering is
    computed from this one ordered, prefetched queryset instead.

    The options are drained into a plain dict here rather than left as related
    managers, so `build_question_index` below can stay query-free.
    """
    questions = list(
        FormQuestion.objects.filter(
            site_id=site_id, form_page__form_id__in=quiz_form_ids
        )
        .select_related("form_page")
        .prefetch_related("options")
        .order_by("form_page__order", "order")
    )
    return questions, {
        question.id: list(question.options.all()) for question in questions
    }


def build_question_index(
    questions: list[FormQuestion],
    options_by_question: dict[UUID, list[QuestionOption]],
) -> QuestionIndex:
    """Number the loaded questions per form and index them for lookup."""
    correct_option_texts: dict[UUID, list[str]] = {
        question.id: [
            option.text
            for option in options_by_question[question.id]
            if option.correct is True
        ]
        for question in questions
    }
    number_by_id: dict[UUID, int] = {}
    per_form_counter: dict[UUID, int] = defaultdict(int)
    by_form: dict[UUID, list[FormQuestion]] = defaultdict(list)
    for question in questions:
        form_id = question.form_page.form_id
        per_form_counter[form_id] += 1
        number_by_id[question.id] = per_form_counter[form_id]
        by_form[form_id].append(question)

    return QuestionIndex(
        question_ids=[question.id for question in questions],
        by_id={question.id: question for question in questions},
        by_form=by_form,
        options_by_question=options_by_question,
        correct_option_texts=correct_option_texts,
        number_by_id=number_by_id,
    )


def load_selected_options_by_pair(
    site_id: int, completed_attempt_ids: list[UUID], question_ids: list[UUID]
) -> dict[tuple[UUID, UUID], list[QuestionOption]]:
    """What each (sitting, question) pair actually had selected.

    The options are drained into a plain dict here rather than left as related
    managers, so `build_sat_questions` below can stay query-free.
    """
    answers = list(
        QuestionAnswer.objects.filter(
            site_id=site_id,
            form_progress_id__in=completed_attempt_ids,
            # The attempt ids cover every form in the cohort's courses, quiz or
            # not. Without this, a survey answer would reach the question lookup
            # in build_sat_questions, which only knows about quiz questions.
            question_id__in=question_ids,
        ).prefetch_related("selected_options")
    )
    return {
        (answer.form_progress_id, answer.question_id): list(
            answer.selected_options.all()
        )
        for answer in answers
    }


def build_sat_questions(
    questions: QuestionIndex,
    forms: FormProgressIndex,
    selected_options_by_pair: dict[tuple[UUID, UUID], list[QuestionOption]],
) -> SatQuestions:
    """Every scorable question each completed sitting covered, and its verdict."""
    # A question left blank stores no answer row, so walking the rows alone would
    # drop it — while it still counts against the learner's score. Pair every
    # completed sitting with every question it covered instead, so a blank one is
    # judged as an empty selection rather than passed over.
    #
    # A completed survey sitting is in completed_attempt_ids too; by_form yields
    # nothing for its form, so it contributes no pairs.
    pairs: list[tuple[UUID, FormQuestion]] = [
        (attempt_id, question)
        for attempt_id in forms.completed_attempt_ids
        for question in questions.by_form.get(
            forms.user_form_by_attempt_id[attempt_id][1], []
        )
        if question.type not in FREE_TEXT_QUESTION_TYPES
    ]
    answer_rows = [
        (
            attempt_id,
            question.id,
            {
                option.id
                for option in selected_options_by_pair.get(
                    (attempt_id, question.id), []
                )
            },
        )
        for attempt_id, question in pairs
    ]
    return SatQuestions(
        pairs=pairs,
        selected_options_by_pair=selected_options_by_pair,
        correctness=evaluate_quiz_answers(answer_rows, questions.options_by_question),
    )


class DistractorRow(TypedDict):
    """One wrong option's selection tally, as the aggregate query returns it.

    `id` is unused downstream but is what makes the aggregate group per option
    rather than per question, so it stays in the `.values()` list.
    """

    question_id: UUID
    id: UUID
    text: str
    times_selected: int


def load_distractor_rows(
    site_id: int, question_ids: list[UUID], first_attempt_ids: set[UUID]
) -> list[DistractorRow]:
    """Wrong-option selection counts, tallied in the database, worst first per question."""
    # `.exclude(correct=True)`, never `.filter(correct=False)`: correct is
    # nullable, and a correct=None option must still count as a distractor.
    rows = (
        QuestionOption.objects.exclude(correct=True)
        .filter(
            site_id=site_id,
            question_id__in=question_ids,
            questionanswer__form_progress_id__in=first_attempt_ids,
        )
        .values("question_id", "id", "text")
        .annotate(times_selected=Count("questionanswer"))
        .order_by("question_id", "-times_selected")
    )
    # `.values()` is typed as plain dicts; the field list above is what fixes
    # the keys, so the shape is named here rather than left loose.
    return cast("list[DistractorRow]", list(rows))


def index_distractors(
    distractor_rows: list[DistractorRow], questions: QuestionIndex
) -> dict[UUID, list[tuple[str, int]]]:
    """Group the loaded distractor rows by question, dropping the ones with no verdict."""
    distractors_by_question: dict[UUID, list[tuple[str, int]]] = defaultdict(list)
    for row in distractor_rows:
        question = questions.by_id.get(row["question_id"])
        if question is None or question.type in FREE_TEXT_QUESTION_TYPES:
            continue
        distractors_by_question[row["question_id"]].append(
            (row["text"], row["times_selected"])
        )
    return distractors_by_question


def resolve_site_name(site_id: int) -> str:
    """The tenant's own display name -- who the report is from.

    HEADER_TITLE first, mirroring how the site header and outbound email
    resolve the same name, so a project that renamed itself in one place is
    not still called something else on its reports. The Site row is read only
    when HEADER_TITLE is unset: the one conditional query in the report
    pipeline, and the `or` is what keeps it conditional.
    """
    return site_config.HEADER_TITLE or Site.objects.get(pk=site_id).name
