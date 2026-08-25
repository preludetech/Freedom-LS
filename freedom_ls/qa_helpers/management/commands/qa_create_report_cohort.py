"""Build a cohort of N learners with a controlled progress distribution.

Written for the cohort progress report QA matrix, which needs cohorts of very
different sizes whose learners carry *genuinely scored* quiz attempts. The
existing helpers cannot do this: ``qa_create_large_cohort`` leaves every learner
with zero progress, and ``qa_create_cohort_progress`` marks progress rows
complete without any answers or scores, so every quiz column, at-risk flag and
confusion tally in the report comes out empty.

What the distribution is tuned for (see ``freedom_ls/reports/gather.py``):

- Completion is recomputed from ``TopicProgress.complete_time`` /
  ``FormProgress.completed_time``; ``CourseProgress.progress_percentage`` is
  never read. Learners are spread across a completion ladder so median
  completion, "not started" and "complete" are all non-degenerate.
- A quiz cell needs ``completed_time`` AND ``scores``, so attempts are completed
  through ``FormProgress.complete()`` rather than by setting a timestamp.
- ``--num-flagged`` is met by mixing all three base at-risk rules: learners with
  no rows at all (``no_activity``), learners whose most recent pass-marked quiz
  attempt fails (``failed_latest_quiz``), and learners whose activity is
  backdated past the 7-day window (``inactive``). Everyone else is kept
  deliberately unflagged, so "No flags" sections exist to check too.
- One learner gets three completed attempts at the first quiz, all wrong on the
  same question. Their own section counts every attempt ("3 times") while the
  cohort confusion tally counts first attempts only -- the two are meant to
  disagree.
- Wrong answers rotate by learner index so the distractor tables show a spread
  of chosen options rather than one bar, and so that on a long quiz every
  question picks up at least one wrong answer (which is what makes the
  "showing worst 10 of N" cap disclosure appear).
- A question the course marked ``required=False`` is missed by being left blank
  rather than by picking a distractor, and no ``QuestionAnswer`` row is written
  for it -- exactly what ``save_answers`` does in the browser. The report scores
  it wrong but has no option text to quote, so its wrong-answer row reads
  "Not answered".

Usage:
    uv run python manage.py qa_create_report_cohort \
        --cohort-name "QA Report Standard Cohort" --num-learners 9 \
        --course-slug qa-report-medium-course --num-flagged 3
    uv run python manage.py qa_create_report_cohort \
        --cohort-name "QA Report Standard Cohort" --num-learners 9 \
        --course-slug qa-report-medium-course \
        --organisation-slug rpas-training-academy
"""

import math
from datetime import datetime, timedelta
from typing import cast

import djclick as click
from allauth.account.models import EmailAddress
from guardian.shortcuts import assign_perm

from django.contrib.sites.models import Site
from django.utils import timezone
from django.utils.text import slugify

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import ContentCollectionItem, Course, Topic
from freedom_ls.form_engine.factories import QuestionAnswerFactory
from freedom_ls.form_engine.models import (
    Form,
    FormProgress,
    FormQuestion,
    FormStrategy,
    QuestionAnswer,
    QuestionOption,
    QuestionType,
)
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
)
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    CohortMembership,
    Learner,
)
from freedom_ls.learner_management.utils import ensure_learner
from freedom_ls.learner_progress.factories import CourseFormAttemptFactory
from freedom_ls.learner_progress.models import (
    CourseFormAttempt,
    CourseProgress,
    TopicProgress,
)
from freedom_ls.learner_progress.signals import recalculate_progress_percentage
from freedom_ls.learner_progress.utils import ensure_course_progress_record
from freedom_ls.organisations.models import Organisation
from freedom_ls.organisations.utils import get_default_organisation

# 40 distinct surnames: the report sorts learners by surname, so creation order
# and alphabetical order are deliberately different.
SURNAMES = [
    "Okonkwo",
    "Delacroix",
    "Bergström",
    "Yusupova",
    "Marchetti",
    "Abara",
    "Thibault",
    "Nakamura",
    "Ferreira",
    "Grimsdóttir",
    "Vasquez",
    "Idowu",
    "Petrov",
    "Chaudhry",
    "Wainwright",
    "Espinoza",
    "Bakalova",
    "Ndlovu",
    "Rasmussen",
    "Quintero",
    "Halloran",
    "Sarkissian",
    "Coetzee",
    "Lindqvist",
    "Mbeki",
    "Fontaine",
    "Ustinov",
    "Achterberg",
    "Whitfield",
    "Jankowski",
    "Ravindran",
    "Solberg",
    "Tanaka",
    "Kowalczyk",
    "Duarte",
    "Ekwueme",
    "Villalobos",
    "Novotný",
    "Zampieri",
    "Hartigan",
]

FIRST_NAMES = [
    "Amara",
    "Theo",
    "Sanne",
    "Rustam",
    "Giulia",
    "Chidi",
    "Margot",
    "Haruki",
    "Ines",
    "Björn",
    "Lucia",
    "Femi",
    "Katya",
    "Zara",
    "Rowan",
    "Mateo",
    "Nadia",
    "Sipho",
    "Freja",
    "Camila",
    "Declan",
    "Anush",
    "Willem",
    "Elsa",
    "Thabo",
    "Colette",
    "Dmitri",
    "Joost",
    "Harriet",
    "Kasia",
    "Anjali",
    "Erik",
    "Yuki",
    "Piotr",
    "Ines",
    "Ngozi",
    "Rafael",
    "Tereza",
    "Enzo",
    "Niamh",
]

# Fraction of the course each unflagged learner has completed. "started" means
# one item opened but nothing completed: has_any_progress is True (so the
# no_activity rule stays quiet) while completion is still 0%.
LADDER: list[str | float] = ["started", 0.2, 0.4, 0.6, 0.8, 1.0]

STATE_NORMAL = "normal"
STATE_NO_ACTIVITY = "no_activity"
STATE_FAILING = "failing"
STATE_STALE = "stale"

RECENT_DAYS_AGO = 2
STALE_DAYS_AGO = 30
# Leaves room for the fixture prefix, the -NN index and the id suffix inside
# the 64-character cap on an email local part.
ORGANISATION_TOKEN_MAX_CHARS = 20
ITEM_SPACING = timedelta(minutes=2)
COURSE_SPACING = timedelta(hours=6)

MULTI_ATTEMPT_COUNT = 3


def _get_site(site_name: str) -> Site:
    try:
        return Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        available = list(Site.objects.values_list("name", flat=True))
        raise click.ClickException(
            f"Site '{site_name}' not found. Available: {available}"
        ) from e


def _get_course(site: Site, slug: str) -> Course:
    try:
        return cast(Course, Course.objects.get(slug=slug, site=site))
    except Course.DoesNotExist as e:
        available = list(
            Course.objects.filter(site=site).values_list("slug", flat=True)
        )
        raise click.ClickException(
            f"Course '{slug}' not found on site '{site.name}'. Available: {available}"
        ) from e


def _get_organisation(site: Site, slug: str) -> Organisation:
    """An existing Organisation on this site, by slug.

    Lookup only: a report cohort belongs to an organisation somebody already
    set up, and silently creating one on a typo would put the fixture where
    nobody is looking for it.
    """
    existing: Organisation | None = Organisation._base_manager.filter(
        slug=slug, site=site
    ).first()
    if existing is None:
        available = list(
            Organisation._base_manager.filter(site=site).values_list("slug", flat=True)
        )
        raise click.ClickException(
            f"Organisation '{slug}' not found on site '{site.name}'. "
            f"Available: {available}"
        )
    return existing


def _get_or_create_user(
    site: Site, email: str, first_name: str, last_name: str
) -> User:
    """A login-ready QA user (password == email), or an existing one made usable."""
    existing: User | None = User.objects.filter(email=email).first()
    if existing is None:
        user = cast(
            User,
            UserFactory(
                email=email,
                first_name=first_name,
                last_name=last_name,
                is_active=True,
                password=email,
                site=site,
            ),
        )
    else:
        user = existing
        user.is_active = True
        user.set_password(email)
        user.save(update_fields=["is_active", "password"])
    EmailAddress.objects.update_or_create(
        user=user,
        email=user.email,
        defaults={"verified": True, "primary": True},
    )
    return user


def _name_for(index: int) -> tuple[str, str]:
    first = FIRST_NAMES[index % len(FIRST_NAMES)]
    last = SURNAMES[index % len(SURNAMES)]
    lap = index // len(SURNAMES)
    return (first, last if lap == 0 else f"{last}-{lap + 1}")


def _learner_states(num_learners: int, num_flagged: int) -> list[str]:
    """One state per learner; the flagged ones are the trailing indices."""
    states = [STATE_NORMAL] * num_learners
    flavours = [STATE_NO_ACTIVITY, STATE_FAILING, STATE_STALE]
    for n in range(min(num_flagged, num_learners)):
        states[num_learners - 1 - n] = flavours[n % len(flavours)]
    return states


def _ladder_value(index: int, states: list[str]) -> str | float:
    """Where on the completion ladder this learner sits.

    The ladder is stretched across the *unflagged* learners rather than cycled
    by index. Cycling silently starves small cohorts: a three-learner cohort
    would only ever sample the bottom three rungs, so nobody would reach a quiz
    and the report's whole quiz and confusion apparatus would come out empty.
    """
    if states[index] == STATE_NO_ACTIVITY:
        # Never read: this learner gets no progress rows at all.
        return LADDER[0]
    if states[index] in (STATE_FAILING, STATE_STALE):
        # Enough progress to have reached a quiz, still spread out.
        return LADDER[2 + (index % (len(LADDER) - 2))]
    normal_indices = [i for i, state in enumerate(states) if state == STATE_NORMAL]
    if len(normal_indices) <= 1:
        return LADDER[-1]
    position = normal_indices.index(index)
    rung = round(position * (len(LADDER) - 1) / (len(normal_indices) - 1))
    return LADDER[rung]


def _max_wrong_for_pass(question_count: int, pass_percentage: int | None) -> int:
    """Most questions a learner can get wrong and still pass this quiz."""
    if pass_percentage is None:
        return max(0, question_count - 1)
    needed = math.ceil(question_count * pass_percentage / 100)
    return max(0, question_count - needed)


def _wrong_orders(
    question_count: int, learner_index: int, quiz_index: int, wrong_count: int
) -> set[int]:
    """Which question orders this learner gets wrong, rotated by learner index.

    Rotating rather than always failing question 1 is what gives the cohort
    confusion section more than one question to rank, and what eventually gives
    every question on a long quiz at least one wrong answer.
    """
    if question_count == 0 or wrong_count <= 0:
        return set()
    start = (learner_index * 3 + quiz_index) % question_count
    return {
        (start + n) % question_count for n in range(min(wrong_count, question_count))
    }


def _choose_options(
    question: FormQuestion,
    options: list[QuestionOption],
    answer_wrong: bool,
    learner_index: int,
) -> list[QuestionOption]:
    """The options this learner ticks. An empty list means they left it blank."""
    correct = [option for option in options if option.correct is True]
    incorrect = [option for option in options if option.correct is not True]
    if not answer_wrong:
        return correct
    if not question.required:
        # An optional question is the only one a learner can actually submit
        # blank (form_fill_page re-renders with 422 for a required one), so
        # missing it is modelled as skipping it. It still scores zero, and the
        # report has nothing to quote back -- which is the "Not answered" cell.
        return []
    if not incorrect:
        # Nothing to pick that is wrong; selecting nothing still scores zero.
        return []
    distractor = incorrect[(learner_index + question.order) % len(incorrect)]
    is_checkbox = question.type == QuestionType.CHECKBOXES
    if is_checkbox and learner_index % 2 == 1:
        # "Everything ticked" is wrong under exact-match scoring too, and it is
        # the case the multi-select scoring fix exists to close.
        return [*correct, distractor]
    return [distractor]


def _complete_attempt(
    record: CourseProgress,
    form: Form,
    collection_item: ContentCollectionItem,
    site: Site,
    questions: list[FormQuestion],
    options_by_question: dict[str, list[QuestionOption]],
    wrong_orders: set[int],
    learner_index: int,
    started_at: datetime,
    completed_at: datetime,
) -> FormProgress:
    """Create one genuinely scored, completed attempt at ``form``."""
    attempt = cast(
        FormProgress,
        CourseFormAttemptFactory(
            course_progress=record,
            form=form,
            collection_item=collection_item,
            site=site,
        ).form_progress,
    )
    for question in questions:
        options = options_by_question[str(question.id)]
        if not options:
            continue
        chosen = _choose_options(
            question, options, question.order in wrong_orders, learner_index
        )
        if not chosen:
            # save_answers writes no QuestionAnswer row for a question the
            # learner left blank, so neither does this. compute_quiz_scores()
            # still counts the question toward max_score, and the report pairs
            # every completed sitting with every question regardless of the
            # rows, so a missing row is judged as an empty selection: wrong,
            # with no chosen option to print.
            continue
        answer = cast(
            QuestionAnswer,
            QuestionAnswerFactory(form_progress=attempt, question=question, site=site),
        )
        answer.selected_options.set(chosen)
    attempt.complete()
    # start_time is auto_now_add and complete() stamps completed_time with now(),
    # so backdating has to happen after the save, via the queryset.
    FormProgress.objects.filter(pk=attempt.pk).update(
        start_time=started_at, completed_time=completed_at
    )
    attempt.refresh_from_db()
    return attempt


def _quiz_questions(
    form: Form,
) -> tuple[list[FormQuestion], dict[str, list[QuestionOption]]]:
    questions = list(
        FormQuestion.objects.filter(form_page__form=form)
        .prefetch_related("options")
        .order_by("form_page__order", "order")
    )
    options_by_question = {
        str(question.id): list(question.options.order_by("order"))
        for question in questions
    }
    return questions, options_by_question


def _last_pass_marked_quiz_slot(items: list[Topic | Form], limit: int) -> int | None:
    """Slot of the last pass-marked quiz within ``items[:limit]``, or None."""
    for slot in range(min(limit, len(items)) - 1, -1, -1):
        item = items[slot]
        if (
            isinstance(item, Form)
            and item.strategy == FormStrategy.QUIZ
            and item.quiz_pass_percentage is not None
        ):
            return slot
    return None


def _first_pass_marked_quiz_slot(items: list[Topic | Form]) -> int | None:
    for slot, item in enumerate(items):
        if (
            isinstance(item, Form)
            and item.strategy == FormStrategy.QUIZ
            and item.quiz_pass_percentage is not None
        ):
            return slot
    return None


def _has_existing_progress(
    record: CourseProgress, collection_items: list[ContentCollectionItem]
) -> bool:
    topic_ids = [ci.child_id for ci in collection_items if isinstance(ci.child, Topic)]
    form_ids = [ci.child_id for ci in collection_items if isinstance(ci.child, Form)]
    return (
        TopicProgress.objects.filter(
            course_progress=record, topic_id__in=topic_ids
        ).exists()
        or CourseFormAttempt.objects.filter(
            course_progress=record, form_progress__form_id__in=form_ids
        ).exists()
    )


def _settle_record(record: CourseProgress) -> None:
    """Bring the record's own figures in line with the rows just written.

    Topic rows are written already complete, so they never make the transition
    the completion receiver watches for -- without this the seeded percentage
    stays at the registration's initial 0 and the educator matrix shows 0%
    beside completed cells.
    """
    recalculate_progress_percentage(record)
    if record.progress_percentage == 100 and record.completed_time is None:
        record.completed_time = timezone.now()
        record.save(update_fields=["completed_time"])


def _generate_course_progress(
    learner: Learner,
    registration: CohortCourseRegistration,
    learner_index: int,
    state: str,
    ladder_value: str | float,
    course: Course,
    course_index: int,
    site: Site,
    is_last_course: bool,
    multi_attempt: bool,
    now: datetime,
) -> None:
    """Create this learner's progress rows for one course."""
    collection_items = [
        ci
        for ci in course.viewable_collection_items()
        if isinstance(ci.child, Topic | Form)
    ]
    if not collection_items or state == STATE_NO_ACTIVITY:
        return

    record = ensure_course_progress_record(learner, course, registration)
    if _has_existing_progress(record, collection_items):
        return

    days_ago = STALE_DAYS_AGO if state == STATE_STALE else RECENT_DAYS_AGO
    base = now - timedelta(days=days_ago) + course_index * COURSE_SPACING

    if ladder_value == "started":
        # One item opened, nothing completed: has_any_progress True, 0% complete.
        first = collection_items[0]
        if isinstance(first.child, Topic):
            TopicProgress.objects.get_or_create(
                course_progress=record,
                collection_item=first,
                defaults={"topic": first.child, "site": site},
            )
        else:
            CourseFormAttemptFactory(
                course_progress=record,
                form=first.child,
                collection_item=first,
                site=site,
            )
        _settle_record(record)
        return

    fraction = cast(float, ladder_value)
    completed_slots = max(1, round(fraction * len(collection_items)))

    items = cast("list[Topic | Form]", [ci.child for ci in collection_items])
    failing_slot: int | None = None
    if state == STATE_FAILING and is_last_course:
        # The failed_latest_quiz rule reads the most recently completed quiz, so
        # the learner has to stop ON a pass-marked quiz for the flag to be the
        # one this fixture is trying to produce.
        failing_slot = _last_pass_marked_quiz_slot(items, completed_slots)
        if failing_slot is None:
            failing_slot = _first_pass_marked_quiz_slot(items)
        if failing_slot is not None:
            completed_slots = failing_slot + 1

    quiz_index = 0
    for slot in range(min(completed_slots, len(collection_items))):
        collection_item = collection_items[slot]
        item = items[slot]
        completed_at = base + slot * ITEM_SPACING
        if isinstance(item, Topic):
            TopicProgress.objects.update_or_create(
                course_progress=record,
                collection_item=collection_item,
                defaults={"topic": item, "complete_time": completed_at, "site": site},
            )
            continue

        if item.strategy != FormStrategy.QUIZ:
            progress = cast(
                FormProgress,
                CourseFormAttemptFactory(
                    course_progress=record,
                    form=item,
                    collection_item=collection_item,
                    site=site,
                ).form_progress,
            )
            progress.complete()
            FormProgress.objects.filter(pk=progress.pk).update(
                start_time=completed_at - ITEM_SPACING, completed_time=completed_at
            )
            continue

        questions, options_by_question = _quiz_questions(item)
        question_count = len(questions)
        if slot == failing_slot:
            needed = math.ceil(question_count * (item.quiz_pass_percentage or 50) / 100)
            wrong_count = question_count - max(0, needed - 1)
        else:
            max_wrong = _max_wrong_for_pass(question_count, item.quiz_pass_percentage)
            wrong_count = learner_index % (max_wrong + 1)
        wrong_orders = _wrong_orders(
            question_count, learner_index, quiz_index, wrong_count
        )

        attempts = MULTI_ATTEMPT_COUNT if (multi_attempt and quiz_index == 0) else 1
        for attempt_number in range(attempts):
            # Earlier attempts are pushed back in time so the first-attempt
            # window function has a deterministic winner.
            offset = (attempts - 1 - attempt_number) * timedelta(hours=1)
            _complete_attempt(
                record=record,
                form=item,
                collection_item=collection_item,
                site=site,
                questions=questions,
                options_by_question=options_by_question,
                wrong_orders=wrong_orders,
                learner_index=learner_index,
                started_at=completed_at - offset - ITEM_SPACING,
                completed_at=completed_at - offset,
            )
        quiz_index += 1

    _settle_record(record)


def organisation_email_prefix(email_prefix: str, organisation: Organisation) -> str:
    """The fixture email prefix, namespaced to one organisation.

    User.email is globally unique and _get_or_create_user matches on it alone,
    so without a per-organisation namespace every organisation's fixture matrix
    is backed by one shared set of User rows. That makes the two matrices
    inseparable: neither can be reset without deleting the other's learners.

    ASCII, because an email local part is: a non-Latin slug transliterates to
    nothing, so those organisations are keyed by their id instead. Truncated,
    because the local part is capped at 64 characters and an organisation slug
    can run to 150 -- and since truncating can make two distinct slugs equal,
    anything that lost information carries the id too.
    """
    base = slugify(organisation.slug or organisation.name)
    token = base[:ORGANISATION_TOKEN_MAX_CHARS]
    if token != base or not token:
        suffix = organisation.id.hex[:6]
        token = f"{token}-{suffix}" if token else suffix
    return f"{email_prefix}-{token}"


def build_report_cohort(
    site: Site,
    cohort_name: str,
    num_learners: int,
    course_slugs: tuple[str, ...],
    inactive_course_slugs: tuple[str, ...],
    num_flagged: int,
    no_progress: bool,
    email_prefix: str,
    educator_email: str | None,
    organisation: Organisation | None = None,
) -> Cohort:
    """Create or reuse the cohort, its members and their progress. Idempotent."""
    now = timezone.now()

    # The site's default organisation when none is named, which is what every
    # fixture built before organisation branding existed already assumed.
    if organisation is None:
        organisation = get_default_organisation(site)

    # Filtered by organisation as well as name: cohort names are unique per
    # organisation, so the same fixture name can legitimately exist in two of
    # them, and looking one up by name alone would rebuild the wrong cohort.
    cohort = cast(
        Cohort,
        Cohort.objects.filter(
            name=cohort_name, site=site, organisation=organisation
        ).first()
        or CohortFactory(name=cohort_name, site=site, organisation=organisation),
    )

    registrations: dict[str, CohortCourseRegistration] = {}
    for slug in (*course_slugs, *inactive_course_slugs):
        course = _get_course(site, slug)
        is_active = slug in course_slugs
        registration = CohortCourseRegistration.objects.filter(
            cohort=cohort, collection=course, site=site
        ).first()
        if registration is None:
            registration = cast(
                CohortCourseRegistration,
                CohortCourseRegistrationFactory(
                    cohort=cohort, collection=course, site=site, is_active=is_active
                ),
            )
        elif registration.is_active != is_active:
            registration.is_active = is_active
            registration.save(update_fields=["is_active"])
        registrations[slug] = registration

    # Progress is generated for active and inactive registrations alike: the
    # report sections an inactive course too, and it must not be empty.
    courses = [
        _get_course(site, slug) for slug in (*course_slugs, *inactive_course_slugs)
    ]
    course_slugs_ordered = [*course_slugs, *inactive_course_slugs]
    states = _learner_states(num_learners, num_flagged)

    # The multi-attempt learner must be someone who completes the whole course,
    # so the repeated quiz is NOT their most recent one and the extra attempts
    # cannot be mistaken for a failed_latest_quiz flag.
    multi_attempt_index: int | None = next(
        (
            index
            for index, state in enumerate(states)
            if state == STATE_NORMAL and _ladder_value(index, states) == 1.0
        ),
        None,
    )

    learners: list[tuple[User, str]] = []
    namespaced_prefix = organisation_email_prefix(email_prefix, organisation)
    for index in range(num_learners):
        first_name, last_name = _name_for(index)
        email = f"{namespaced_prefix}-{index + 1:02d}@email.com"
        user = _get_or_create_user(site, email, first_name, last_name)
        if not CohortMembership.objects.filter(
            learner__user=user, cohort=cohort, site=site
        ).exists():
            CohortMembershipFactory(
                learner__user=user,
                learner__organisation=cohort.organisation,
                cohort=cohort,
                site=site,
            )
        learners.append((user, states[index]))

        if no_progress:
            continue

        learner = ensure_learner(user, cohort.organisation)
        state = states[index]
        ladder_value = _ladder_value(index, states)
        for course_index, (course, slug) in enumerate(
            zip(courses, course_slugs_ordered, strict=True)
        ):
            _generate_course_progress(
                learner=learner,
                registration=registrations[slug],
                learner_index=index,
                state=state,
                ladder_value=ladder_value,
                course=course,
                course_index=course_index,
                site=site,
                is_last_course=course_index == len(courses) - 1,
                multi_attempt=index == multi_attempt_index,
                now=now,
            )

    if educator_email:
        educator = _get_or_create_user(site, educator_email, "Quinn", "Reporter")
        assign_perm("view_cohort", educator, cohort)

    return cohort


@click.command()
@click.option(
    "--site-name",
    default="DemoDev",
    help="Site name to create the data on (default: 'DemoDev').",
)
@click.option("--cohort-name", required=True, help="Name of the cohort to build.")
@click.option(
    "--num-learners",
    default=9,
    type=int,
    help="How many learners to put in the cohort.",
)
@click.option(
    "--course-slug",
    multiple=True,
    help="Course slug to register the cohort for (active). Repeatable.",
)
@click.option(
    "--inactive-course-slug",
    multiple=True,
    help="Course slug registered with is_active=False. Repeatable.",
)
@click.option(
    "--num-flagged",
    default=0,
    type=int,
    help=(
        "How many learners should trip an at-risk rule. Cycles through "
        "no-activity / failed-latest-quiz / inactive."
    ),
)
@click.option(
    "--no-progress",
    is_flag=True,
    default=False,
    help="Create members with no progress rows at all.",
)
@click.option(
    "--email-prefix",
    default="qa-report-learner",
    help="Email stem; learners are <prefix>-01@email.com upwards.",
)
@click.option(
    "--educator-email",
    default=None,
    help="Optional educator to create and grant guardian 'view_cohort' on this cohort.",
)
@click.option(
    "--organisation-slug",
    default=None,
    help=(
        "Slug of an existing organisation to put the cohort in "
        "(default: the site's default organisation)."
    ),
)
def command(
    site_name: str,
    cohort_name: str,
    num_learners: int,
    course_slug: tuple[str, ...],
    inactive_course_slug: tuple[str, ...],
    num_flagged: int,
    no_progress: bool,
    email_prefix: str,
    educator_email: str | None,
    organisation_slug: str | None,
) -> None:
    """Build a cohort with a controlled progress and at-risk distribution."""
    site = _get_site(site_name)
    organisation = (
        _get_organisation(site, organisation_slug) if organisation_slug else None
    )
    cohort = build_report_cohort(
        site=site,
        cohort_name=cohort_name,
        num_learners=num_learners,
        course_slugs=course_slug,
        inactive_course_slugs=inactive_course_slug,
        num_flagged=num_flagged,
        no_progress=no_progress,
        email_prefix=email_prefix,
        educator_email=educator_email,
        organisation=organisation,
    )

    registrations = list(
        CohortCourseRegistration.objects.filter(
            cohort=cohort, site=site
        ).select_related("collection")
    )
    member_count = CohortMembership.objects.filter(cohort=cohort, site=site).count()

    click.secho("\n--- QA report cohort ---", fg="cyan", bold=True)
    click.secho(f"Site:     {site.name} ({site.domain})", fg="cyan")
    click.secho(f"Cohort:   {cohort.name} (pk={cohort.pk})", fg="cyan", bold=True)
    click.secho(
        f"Org:      {cohort.organisation.name} "
        f"({'has logo' if cohort.organisation.logo else 'no logo'})",
        fg="cyan",
    )
    click.secho(f"Learners: {member_count}", fg="cyan")
    click.secho(
        f"Logins:   {email_prefix}-NN@email.com (password == email)", fg="green"
    )
    for registration in registrations:
        state = "active" if registration.is_active else "INACTIVE"
        click.secho(
            f"  course: {registration.collection.title} "
            f"[{registration.collection.slug}] ({state})",
            fg="green",
        )
    if educator_email:
        click.secho(
            f"Educator: {educator_email} / {educator_email} (view_cohort granted)",
            fg="green",
            bold=True,
        )
    click.secho(
        f"Panel:    /educator/organisations/{cohort.organisation.slug}"
        f"/cohorts/{cohort.pk}",
        fg="cyan",
    )
