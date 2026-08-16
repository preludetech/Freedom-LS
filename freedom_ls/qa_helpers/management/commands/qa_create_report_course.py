"""Build a self-contained QA course of a given length and quiz count.

The cohort progress report's landscape summary table gets one data column per
QUIZ form in the course, so the report's layout behaviour is driven by the
course's *quiz* count as much as its item count. ``qa_add_course_items_for_pagination``
appends Topics only and therefore cannot build the long course the report QA
matrix needs.

Courses built here are standalone: every Topic and Form belongs to exactly one
QA course (slugs carry the course key). That matters because ``TopicProgress``
is ``unique_together(user, topic)`` -- a Topic shared between two fixture
courses would leak one course's completion into the other's percentages.

Quizzes are built from option-backed questions only (``multiple_choice`` and
``checkboxes``). ``FormProgress.score_quiz()`` counts every question toward
``max_score`` and a free-text question can never be scored correct, so a quiz
containing one would sit under a permanent score ceiling and make every pass
mark meaningless.

Idempotent and additive: re-running with a larger ``--num-quizzes`` appends the
missing quizzes and re-lays the whole course out, which is the loop the
landscape column-budget check needs.

Usage:
    uv run python manage.py qa_create_report_course --course-key short \
        --num-items 4 --num-quizzes 1
    uv run python manage.py qa_create_report_course --course-key long \
        --num-items 30 --num-quizzes 12 --questions-per-quiz 6
"""

from typing import cast

import djclick as click

from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site

from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
    QuestionOptionFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import (
    ContentCollectionItem,
    Course,
    Form,
    FormPage,
    FormQuestion,
    FormStrategy,
    QuestionType,
    Topic,
)

# Deliberately not in alphabetical order: the report orders quiz columns by
# their position in the course, and that is only falsifiable when course order
# and alphabetical order disagree.
TOPIC_WORDS = [
    "Signals",
    "Anatomy",
    "Vectors",
    "Ecology",
    "Rhythm",
    "Bridges",
    "Ozone",
    "Kernels",
    "Deltas",
    "Wetlands",
    "Cadence",
    "Isotopes",
    "Glaciers",
    "Pigments",
    "Turbines",
    "Lattices",
    "Neurons",
    "Estuaries",
    "Foraging",
    "Magnets",
    "Beacons",
    "Currents",
    "Harvest",
    "Quarries",
    "Prisms",
    "Aquifers",
    "Sediment",
    "Yeasts",
    "Junctions",
    "Compasses",
]

QUIZ_WORDS = [
    "Voltage",
    "Erosion",
    "Tempo",
    "Alloys",
    "Photons",
    "Mycology",
    "Basalt",
    "Ledgers",
    "Osmosis",
    "Ratios",
    "Fossils",
    "Hydrology",
    "Circuits",
    "Nutrients",
    "Dialects",
    "Gearing",
    "Plumage",
    "Streams",
    "Metrics",
    "Cartography",
]


def _get_site(site_name: str) -> Site:
    try:
        return Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        available = list(Site.objects.values_list("name", flat=True))
        raise click.ClickException(
            f"Site '{site_name}' not found. Available: {available}"
        ) from e


def _word(pool: list[str], index: int) -> str:
    """A stable word for the given index, suffixed once the pool wraps."""
    word = pool[index % len(pool)]
    lap = index // len(pool)
    return word if lap == 0 else f"{word} {lap + 1}"


def quiz_positions(num_items: int, num_quizzes: int) -> list[int]:
    """Evenly spread slot indices for the quizzes among ``num_items`` slots.

    Spreading rather than appending matters: a course whose quizzes all sit at
    the end never exercises a quiz column ordered before a topic.
    """
    if num_quizzes <= 0 or num_items <= 0:
        return []
    taken: set[int] = set()
    positions: list[int] = []
    for q in range(num_quizzes):
        slot = round((q + 0.5) * num_items / num_quizzes)
        slot = max(0, min(slot, num_items - 1))
        while slot in taken:
            slot = (slot + 1) % num_items
        taken.add(slot)
        positions.append(slot)
    return positions


def _get_or_create_course(site: Site, course_key: str) -> Course:
    slug = f"qa-report-{course_key}-course"
    existing: Course | None = Course.objects.filter(slug=slug, site=site).first()
    if existing is not None:
        return existing
    return cast(
        Course,
        CourseFactory(
            title=f"QA Report {course_key.title()} Course",
            slug=slug,
            description=(
                f"Standalone QA course for the cohort progress report "
                f"({course_key} length)."
            ),
            site=site,
        ),
    )


def _get_or_create_topic(site: Site, course_key: str, index: int) -> Topic:
    slug = f"qa-report-{course_key}-topic-{index + 1:02d}"
    existing: Topic | None = Topic.objects.filter(slug=slug, site=site).first()
    if existing is not None:
        return existing
    word = _word(TOPIC_WORDS, index)
    return cast(
        Topic,
        TopicFactory(
            title=f"{word} Lesson {index + 1:02d}",
            slug=slug,
            content=f"QA report fixture topic covering {word.lower()}.",
            site=site,
        ),
    )


def _add_options(
    question: FormQuestion, options: list[tuple[str, bool]], site: Site
) -> None:
    for i, (text, correct) in enumerate(options):
        QuestionOptionFactory(
            question=question,
            text=text,
            value=str(i + 1),
            order=i,
            correct=correct,
            site=site,
        )


def _ensure_questions(
    form: Form, page: FormPage, subject: str, question_count: int, site: Site
) -> None:
    """Add option-backed questions until the page holds ``question_count`` of them."""
    existing_orders = set(
        FormQuestion.objects.filter(form_page=page).values_list("order", flat=True)
    )
    for order in range(question_count):
        if order in existing_orders:
            continue
        is_checkbox = order % 2 == 1
        stem = f"{subject} Q{order + 1:02d}"
        question = cast(
            FormQuestion,
            FormQuestionFactory(
                form_page=page,
                question=(
                    f"{stem}: which two statements about {subject.lower()} hold?"
                    if is_checkbox
                    else f"{stem}: which statement about {subject.lower()} holds?"
                ),
                type=(
                    QuestionType.CHECKBOXES
                    if is_checkbox
                    else QuestionType.MULTIPLE_CHOICE
                ),
                required=True,
                order=order,
                site=site,
            ),
        )
        if is_checkbox:
            options = [
                (f"{stem} option A (correct)", True),
                (f"{stem} option B (correct)", True),
                (f"{stem} option C", False),
            ]
        else:
            options = [
                (f"{stem} option A (correct)", True),
                (f"{stem} option B", False),
                (f"{stem} option C", False),
            ]
        _add_options(question, options, site)


def _get_or_create_quiz(
    site: Site,
    course_key: str,
    index: int,
    question_count: int,
    pass_percentage: int | None,
) -> Form:
    slug = f"qa-report-{course_key}-quiz-{index + 1:02d}"
    word = _word(QUIZ_WORDS, index)
    existing: Form | None = Form.objects.filter(slug=slug, site=site).first()
    if existing is not None:
        form = existing
        # Re-runs converge: which quiz is "last" changes when --num-quizzes
        # grows, so the pass mark is rewritten rather than left as first built.
        if form.quiz_pass_percentage != pass_percentage:
            form.quiz_pass_percentage = pass_percentage
            form.save(update_fields=["quiz_pass_percentage"])
        page = cast(
            FormPage, FormPage.objects.filter(form=form).order_by("order").first()
        )
    else:
        form = cast(
            Form,
            FormFactory(
                title=f"{word} Quiz {index + 1:02d}",
                slug=slug,
                strategy=FormStrategy.QUIZ,
                quiz_show_incorrect=True,
                quiz_pass_percentage=pass_percentage,
                site=site,
            ),
        )
        page = cast(
            FormPage,
            FormPageFactory(
                form=form,
                title=f"{word} Quiz Page",
                slug=f"{slug}-page",
                order=0,
                site=site,
            ),
        )
    _ensure_questions(form, page, word, question_count, site)
    return form


def _lay_out_course(course: Course, plan: list[Topic | Form], site: Site) -> None:
    """Attach every planned item to the course at its planned order (idempotent)."""
    course_ctype = ContentType.objects.get_for_model(Course)
    existing = {
        (link.child_type_id, link.child_id): link
        for link in ContentCollectionItem.objects.filter(
            collection_type=course_ctype, collection_id=course.pk, site=site
        )
    }
    for order, item in enumerate(plan):
        child_ctype = ContentType.objects.get_for_model(item)
        link = existing.get((child_ctype.pk, item.pk))
        if link is None:
            ContentCollectionItemFactory(
                collection_object=course,
                child_object=item,
                order=order,
                site=site,
            )
        elif link.order != order:
            link.order = order
            link.save(update_fields=["order"])


def build_report_course(
    site: Site,
    course_key: str,
    num_items: int,
    num_quizzes: int,
    questions_per_quiz: int,
    big_quiz_questions: int,
    pass_percentage: int,
    no_pass_mark_quiz: bool,
) -> Course:
    """Create or extend the QA report course and return it.

    Exposed as a function so ``qa_create_report_fixtures`` can build the whole
    matrix in one process instead of shelling out per course.
    """
    if num_quizzes > num_items:
        raise click.ClickException(
            f"--num-quizzes ({num_quizzes}) cannot exceed --num-items ({num_items})."
        )

    course = _get_or_create_course(site, course_key)
    positions = set(quiz_positions(num_items, num_quizzes))

    plan: list[Topic | Form] = []
    quiz_index = 0
    topic_index = 0
    for slot in range(num_items):
        if slot in positions:
            question_count = (
                big_quiz_questions
                if quiz_index == 0 and big_quiz_questions > 0
                else questions_per_quiz
            )
            # The no-pass-mark quiz is the FIRST one: it sits earliest in the
            # course, so most of the cohort reaches it and the "score but no
            # verdict" column has real data in it rather than one lone cell.
            quiz_pass = (
                None if (no_pass_mark_quiz and quiz_index == 0) else pass_percentage
            )
            plan.append(
                _get_or_create_quiz(
                    site, course_key, quiz_index, question_count, quiz_pass
                )
            )
            quiz_index += 1
        else:
            plan.append(_get_or_create_topic(site, course_key, topic_index))
            topic_index += 1

    # Every link is written before any viewable_items() read: Course.children()
    # is memoized per instance, so a link created after a read reports stale.
    _lay_out_course(course, plan, site)
    return cast(Course, Course.objects.get(pk=course.pk))


@click.command()
@click.option(
    "--site-name",
    default="DemoDev",
    help="Site name to create the data on (default: 'DemoDev').",
)
@click.option(
    "--course-key",
    required=True,
    help="Short key for the course, e.g. 'short' -> slug 'qa-report-short-course'.",
)
@click.option(
    "--num-items",
    default=12,
    type=int,
    help="Total viewable items (topics + quizzes) the course should hold.",
)
@click.option(
    "--num-quizzes",
    default=3,
    type=int,
    help="How many of those items are QUIZ forms (one report column each).",
)
@click.option(
    "--questions-per-quiz",
    default=4,
    type=int,
    help="Option-backed questions per quiz (default: 4).",
)
@click.option(
    "--big-quiz-questions",
    default=0,
    type=int,
    help=(
        "If >0, the first quiz gets this many questions. Use >10 to make the "
        "report's 'showing worst 10 of N' confusion cap disclosure appear."
    ),
)
@click.option(
    "--pass-percentage",
    default=50,
    type=int,
    help="quiz_pass_percentage for every quiz (default: 50).",
)
@click.option(
    "--no-pass-mark-quiz",
    is_flag=True,
    default=False,
    help="Leave the FIRST quiz's quiz_pass_percentage unset (score, no verdict).",
)
def command(
    site_name: str,
    course_key: str,
    num_items: int,
    num_quizzes: int,
    questions_per_quiz: int,
    big_quiz_questions: int,
    pass_percentage: int,
    no_pass_mark_quiz: bool,
) -> None:
    """Build a standalone QA course of a given length and quiz count."""
    site = _get_site(site_name)
    course = build_report_course(
        site=site,
        course_key=course_key,
        num_items=num_items,
        num_quizzes=num_quizzes,
        questions_per_quiz=questions_per_quiz,
        big_quiz_questions=big_quiz_questions,
        pass_percentage=pass_percentage,
        no_pass_mark_quiz=no_pass_mark_quiz,
    )

    items = course.viewable_items()
    quizzes = [
        item
        for item in items
        if isinstance(item, Form) and item.strategy == FormStrategy.QUIZ
    ]

    click.secho("\n--- QA report course ---", fg="cyan", bold=True)
    click.secho(f"Site:    {site.name} ({site.domain})", fg="cyan")
    click.secho(f"Course:  {course.title}  [slug: {course.slug}]", fg="cyan", bold=True)
    click.secho(
        f"Items:   {len(items)} viewable ({len(items) - len(quizzes)} topics, "
        f"{len(quizzes)} quizzes)",
        fg="cyan",
    )
    click.secho("Quiz columns, in course order:", fg="cyan")
    for position, quiz in enumerate(items):
        if not (isinstance(quiz, Form) and quiz.strategy == FormStrategy.QUIZ):
            continue
        question_count = FormQuestion.objects.filter(form_page__form=quiz).count()
        pass_mark = (
            "no pass mark"
            if quiz.quiz_pass_percentage is None
            else f"pass {quiz.quiz_pass_percentage}%"
        )
        click.secho(
            f"  item {position + 1:>2}  {quiz.title}  "
            f"({question_count} questions, {pass_mark})",
            fg="green",
        )
