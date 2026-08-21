"""Craft a legacy (pre-fix) checkbox attempt whose stored score is now wrong.

QA 12.6 needs a completed attempt from *before* multi-select scoring became
exact-set-match: a ``checkboxes`` answer that selected **every** option (both
correct ones and the incorrect one), which the old "any correct option
selected" rule credited as correct. Historical attempts are never rescored, so
the stored ``FormProgress.scores`` must keep that inflated number while every
freshly computed view of the same answer (the results page's incorrect-answers
review, and the report's wrong-answer detail) now calls it wrong.

There is no way to produce that state through the UI - ``FormProgress.complete()``
scores with today's rule - so this command completes the attempt normally and
then re-stamps ``scores`` with the pre-fix value via ``queryset.update()``.

Built idempotently on the requested site:

* Course ``qa-legacy-score-course``: item 1 is the quiz (so it is reachable
  without walking any earlier item), item 2 is a topic so completion is
  partial and the report has something to differ on.
* Quiz ``qa-legacy-score-quiz-form``: pass mark 80%, ``quiz_show_incorrect``
  on. Q1 is ``checkboxes`` (3 options, 2 correct), Q2 is ``multiple_choice``
  (3 options, 1 correct). Stored legacy score 2/2 = 100% (PASS); recomputed
  exact-match score 1/2 = 50% (FAIL).
* Three students in cohort *QA Legacy Score Discrepancy Cohort*, which is
  registered for the course so a cohort PDF report can be generated for it:
  the legacy attempt, an honest attempt where stored and recomputed agree, and
  one student with no activity at all.

Usage:
    uv run python manage.py qa_create_legacy_checkbox_score
    uv run python manage.py qa_create_legacy_checkbox_score --site-name DemoDev
"""

from typing import cast

import djclick as click
from allauth.account.models import EmailAddress
from guardian.shortcuts import assign_perm

from django.contrib.sites.models import Site
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
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
    Course,
    Form,
    FormPage,
    FormQuestion,
    FormStrategy,
    QuestionOption,
    QuestionType,
    Topic,
)
from freedom_ls.organisations.utils import get_default_organisation
from freedom_ls.student_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    UserCourseRegistrationFactory,
)
from freedom_ls.student_management.models import (
    Cohort,
    CohortCourseRegistration,
    CohortMembership,
    UserCourseRegistration,
)
from freedom_ls.student_progress.factories import (
    CourseProgressFactory,
    FormProgressFactory,
    QuestionAnswerFactory,
    TopicProgressFactory,
)
from freedom_ls.student_progress.models import (
    CourseProgress,
    FormProgress,
    QuestionAnswer,
    TopicProgress,
)
from freedom_ls.student_progress.scoring import is_quiz_answer_correct

COURSE_TITLE = "QA Legacy Checkbox Score Course"
COURSE_SLUG = "qa-legacy-score-course"

FORM_TITLE = "QA Legacy Checkbox Score Quiz"
FORM_SLUG = "qa-legacy-score-quiz-form"
PASS_PERCENTAGE = 80

PAGE_TITLE = "QA Legacy Checkbox Score Page"
PAGE_SLUG = "qa-legacy-score-quiz-page"

TOPIC_TITLE = "QA Legacy Score Follow-Up Topic"
TOPIC_SLUG = "qa-legacy-score-topic"

CHECKBOX_QUESTION = "Which TWO of these are correct? (legacy scoring fixture)"
CHECKBOX_OPTIONS: list[tuple[str, bool]] = [
    ("Correct option A", True),
    ("Correct option B", True),
    ("Incorrect option C - selecting this is now wrong", False),
]

MC_QUESTION = "Pick the one correct answer (legacy scoring fixture)"
MC_OPTIONS: list[tuple[str, bool]] = [
    ("MC correct answer", True),
    ("MC wrong answer A", False),
    ("MC wrong answer B", False),
]

COHORT_NAME = "QA Legacy Score Discrepancy Cohort"

LEGACY_EMAIL = "demodev_legacyscore@email.com"
CURRENT_EMAIL = "demodev_legacyscore_current@email.com"
IDLE_EMAIL = "demodev_legacyscore_idle@email.com"

# Optional: the report-fixture educator, if that fixture set has been seeded.
OPTIONAL_EDUCATOR_EMAIL = "qa-report-educator@email.com"


def _get_site(site_name: str) -> Site:
    try:
        return Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        available = list(Site.objects.values_list("name", flat=True))
        raise click.ClickException(
            f"Site '{site_name}' not found. Available: {available}"
        ) from e


def _get_or_create_user(
    site: Site, email: str, first_name: str, last_name: str
) -> tuple[User, bool]:
    """Login-ready QA user (password == email), reused if already present."""
    existing: User | None = User.objects.filter(email=email).first()
    if existing is not None:
        existing.is_active = True
        existing.set_password(email)
        existing.save(update_fields=["is_active", "password"])
        user, created = existing, False
    else:
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
        created = True

    EmailAddress.objects.update_or_create(
        user=user,
        email=user.email,
        defaults={"verified": True, "primary": True},
    )
    return user, created


def _get_or_create_course(site: Site) -> Course:
    existing: Course | None = Course.objects.filter(slug=COURSE_SLUG, site=site).first()
    if existing is not None:
        return existing
    return cast(
        Course,
        CourseFactory(
            title=COURSE_TITLE,
            slug=COURSE_SLUG,
            description=(
                "QA course holding a pre-fix checkbox attempt whose stored score "
                "disagrees with today's exact-match scoring."
            ),
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


def _build_quiz(site: Site) -> Form:
    """QUIZ form with one checkboxes and one multiple_choice question. Idempotent."""
    existing: Form | None = Form.objects.filter(slug=FORM_SLUG, site=site).first()
    if existing is not None:
        return existing

    form = cast(
        Form,
        FormFactory(
            title=FORM_TITLE,
            slug=FORM_SLUG,
            strategy=FormStrategy.QUIZ,
            quiz_show_incorrect=True,
            quiz_pass_percentage=PASS_PERCENTAGE,
            site=site,
        ),
    )
    page = cast(
        FormPage,
        FormPageFactory(
            form=form, title=PAGE_TITLE, slug=PAGE_SLUG, order=0, site=site
        ),
    )

    checkbox_question = cast(
        FormQuestion,
        FormQuestionFactory(
            form_page=page,
            question=CHECKBOX_QUESTION,
            type=QuestionType.CHECKBOXES,
            required=True,
            order=0,
            site=site,
        ),
    )
    _add_options(checkbox_question, CHECKBOX_OPTIONS, site)

    mc_question = cast(
        FormQuestion,
        FormQuestionFactory(
            form_page=page,
            question=MC_QUESTION,
            type=QuestionType.MULTIPLE_CHOICE,
            required=True,
            order=1,
            site=site,
        ),
    )
    _add_options(mc_question, MC_OPTIONS, site)

    return form


def _get_or_create_topic(site: Site) -> Topic:
    existing: Topic | None = Topic.objects.filter(slug=TOPIC_SLUG, site=site).first()
    if existing is not None:
        return existing
    return cast(
        Topic,
        TopicFactory(
            title=TOPIC_TITLE,
            slug=TOPIC_SLUG,
            content=(
                "# Follow-up\n\nA second course item so cohort completion is "
                "partial for the student holding the legacy attempt.\n"
            ),
            site=site,
        ),
    )


def _attach(course: Course, child: Form | Topic, order: int, site: Site) -> None:
    already = any(item.child_id == child.pk for item in course.items.all())
    if not already:
        ContentCollectionItemFactory(
            collection_object=course, child_object=child, order=order, site=site
        )


def _register(user: User, course: Course, site: Site) -> None:
    if not UserCourseRegistration.objects.filter(
        user=user, collection=course, site=site
    ).exists():
        UserCourseRegistrationFactory(
            user=user,
            collection=course,
            site=site,
            organisation=get_default_organisation(site),
        )


def _ensure_course_progress_row(user: User, course: Course, site: Site) -> None:
    """Pre-create CourseProgress WITH a site.

    Completing a Topic or Form fires ``update_course_progress_on_completion``,
    which calls ``CourseProgress.objects.update_or_create()`` without a site and
    violates the NOT NULL constraint unless the row already exists.
    """
    if not CourseProgress.objects.filter(user=user, course=course, site=site).exists():
        CourseProgressFactory(user=user, course=course, site=site)


def _answer(
    attempt: FormProgress,
    question: FormQuestion,
    options: list[QuestionOption],
    site: Site,
) -> None:
    answer: QuestionAnswer | None = QuestionAnswer.objects.filter(
        form_progress=attempt, question=question
    ).first()
    if answer is None:
        answer = cast(
            QuestionAnswer,
            QuestionAnswerFactory(form_progress=attempt, question=question, site=site),
        )
    answer.selected_options.set(options)


def _complete_attempt(
    user: User, form: Form, site: Site, *, select_every_checkbox_option: bool
) -> FormProgress:
    """Create one completed attempt, scored with today's exact-match rule.

    The multiple_choice question is always answered correctly. The checkboxes
    question is answered either with every option (the legacy shape: both
    correct options plus the incorrect one) or with the correct options only.
    """
    attempt: FormProgress | None = FormProgress.objects.filter(
        user=user, form=form, site=site
    ).first()
    if attempt is None:
        attempt = cast(
            FormProgress, FormProgressFactory(user=user, form=form, site=site)
        )

    for question in FormQuestion.objects.filter(form_page__form=form).order_by("order"):
        options = list(question.options.order_by("order"))
        if not options:
            continue
        if question.type == QuestionType.CHECKBOXES and select_every_checkbox_option:
            chosen = options
        else:
            chosen = [o for o in options if o.correct is True]
        _answer(attempt, question, chosen, site)

    attempt.complete()
    attempt.refresh_from_db()
    return attempt


def _recomputed_score(attempt: FormProgress) -> tuple[int, int]:
    """Score the stored answers with today's exact-set-match rule."""
    score = 0
    max_score = 0
    for question in FormQuestion.objects.filter(
        form_page__form=attempt.form
    ).prefetch_related("options"):
        max_score += 1
        answer: QuestionAnswer | None = QuestionAnswer.objects.filter(
            form_progress=attempt, question=question
        ).first()
        if answer is None:
            continue
        selected = {o.id for o in answer.selected_options.all()}
        if is_quiz_answer_correct(selected, question.options.all()):
            score += 1
    return score, max_score


def _legacy_score(attempt: FormProgress) -> tuple[int, int]:
    """Score the stored answers with the pre-fix rule.

    Before the fix a multi-select question counted as correct as soon as *any*
    correct option was selected, regardless of the incorrect options ticked
    alongside it.
    """
    score = 0
    max_score = 0
    for question in FormQuestion.objects.filter(
        form_page__form=attempt.form
    ).prefetch_related("options"):
        max_score += 1
        answer: QuestionAnswer | None = QuestionAnswer.objects.filter(
            form_progress=attempt, question=question
        ).first()
        if answer is None:
            continue
        selected = {o.id for o in answer.selected_options.all()}
        correct_ids = {o.id for o in question.options.all() if o.correct is True}
        if correct_ids & selected:
            score += 1
    return score, max_score


def _stamp_legacy_score(attempt: FormProgress) -> tuple[dict[str, int], dict[str, int]]:
    """Overwrite the stored score with the pre-fix number. Returns (stored, recomputed).

    ``queryset.update()`` rather than ``save()``: nothing on this row should be
    rescored or re-trigger the completion hook, and ``last_updated_time`` is
    ``auto_now``.
    """
    legacy_score, legacy_max = _legacy_score(attempt)
    stored = {"score": legacy_score, "max_score": legacy_max}
    FormProgress.objects.filter(pk=attempt.pk).update(scores=stored)
    attempt.refresh_from_db()
    recomputed_score, recomputed_max = _recomputed_score(attempt)
    return stored, {"score": recomputed_score, "max_score": recomputed_max}


def _complete_topic(user: User, topic: Topic, site: Site) -> None:
    progress: TopicProgress | None = TopicProgress.objects.filter(
        user=user, topic=topic
    ).first()
    if progress is None:
        progress = cast(
            TopicProgress, TopicProgressFactory(user=user, topic=topic, site=site)
        )
    if progress.complete_time is None:
        progress.complete_time = timezone.now()
        progress.save()


def _get_or_create_cohort(site: Site) -> Cohort:
    existing: Cohort | None = Cohort.objects.filter(name=COHORT_NAME, site=site).first()
    if existing is not None:
        return existing
    return cast(
        Cohort,
        CohortFactory(
            name=COHORT_NAME, site=site, organisation=get_default_organisation(site)
        ),
    )


def _register_cohort(cohort: Cohort, course: Course, site: Site) -> None:
    if not CohortCourseRegistration.objects.filter(
        cohort=cohort, collection=course, site=site
    ).exists():
        CohortCourseRegistrationFactory(cohort=cohort, collection=course, site=site)


def _add_member(user: User, cohort: Cohort, site: Site) -> None:
    if not CohortMembership.objects.filter(
        user=user, cohort=cohort, site=site
    ).exists():
        CohortMembershipFactory(user=user, cohort=cohort, site=site)


def _item_index(course: Course, child: Form | Topic) -> int:
    for i, item in enumerate(course.viewable_items()):
        if item.pk == child.pk:
            return i + 1
    raise click.ClickException(
        f"'{child.slug}' is not a viewable item of course '{course.slug}'."
    )


@click.command()
@click.option(
    "--site-name",
    default="DemoDev",
    help="Site name to create the data on (default: 'DemoDev').",
)
def command(site_name: str) -> None:
    """Craft a pre-fix checkbox attempt whose stored score is now too high."""
    site = _get_site(site_name)

    course = _get_or_create_course(site)
    quiz = _build_quiz(site)
    topic = _get_or_create_topic(site)
    # Write every collection item before the first viewable_items() read:
    # Course.children() memoizes on the instance.
    _attach(course, quiz, 0, site)
    _attach(course, topic, 1, site)
    quiz_index = _item_index(course, quiz)
    topic_index = _item_index(course, topic)

    cohort = _get_or_create_cohort(site)
    _register_cohort(cohort, course, site)

    legacy_user, legacy_created = _get_or_create_user(
        site, LEGACY_EMAIL, "Lena", "Legacy"
    )
    current_user, current_created = _get_or_create_user(
        site, CURRENT_EMAIL, "Cari", "Current"
    )
    idle_user, idle_created = _get_or_create_user(
        site, IDLE_EMAIL, "Nils", "NoActivity"
    )

    for user in (legacy_user, current_user, idle_user):
        _register(user, course, site)
        _add_member(user, cohort, site)
    for user in (legacy_user, current_user):
        _ensure_course_progress_row(user, course, site)

    # The legacy attempt: every checkbox option selected, stored score re-stamped
    # to what the pre-fix rule would have produced.
    legacy_attempt = _complete_attempt(
        legacy_user, quiz, site, select_every_checkbox_option=True
    )
    stored, recomputed = _stamp_legacy_score(legacy_attempt)

    # A present-day attempt where stored and recomputed agree, for contrast.
    current_attempt = _complete_attempt(
        current_user, quiz, site, select_every_checkbox_option=False
    )
    _complete_topic(current_user, topic, site)

    educator = User.objects.filter(email=OPTIONAL_EDUCATOR_EMAIL, site=site).first()
    if educator is not None:
        assign_perm("view_cohort", educator, cohort)

    stored_pct = round(stored["score"] / stored["max_score"] * 100)
    recomputed_pct = round(recomputed["score"] / recomputed["max_score"] * 100)

    click.secho(
        "\n--- Legacy checkbox score discrepancy (QA 12.6) ---", fg="cyan", bold=True
    )
    click.secho(f"Site:   {site.name} ({site.domain}) [id {site.pk}]", fg="cyan")
    click.secho(f"Course: {course.title}  [slug: {course.slug}]", fg="cyan")
    click.secho(
        f"Quiz:   {quiz.title}  [slug: {quiz.slug}, pass mark {quiz.quiz_pass_percentage}%, "
        f"show_incorrect {quiz.quiz_show_incorrect}]",
        fg="cyan",
    )
    click.echo(f"Topic:  {topic.title}  [slug: {topic.slug}, item {topic_index}]")

    click.secho("\nLogins (password == email):", fg="cyan", bold=True)
    for user, created, note in (
        (
            legacy_user,
            legacy_created,
            "legacy attempt - stored score is the pre-fix one",
        ),
        (current_user, current_created, "present-day attempt, stored == recomputed"),
        (idle_user, idle_created, "no activity at all"),
    ):
        click.secho(
            f"  {'created' if created else 'reused':>7}  {user.email}  ({note})",
            fg="green",
        )

    click.secho("\nThe crafted attempt:", fg="cyan", bold=True)
    click.echo(f"  student            : {legacy_user.email}")
    click.echo(
        f"  checkbox selection : every option ({len(CHECKBOX_OPTIONS)} of {len(CHECKBOX_OPTIONS)})"
    )
    click.secho(
        f"  STORED   scores    : {stored} = {stored_pct}% "
        f"-> {'PASS' if stored_pct >= PASS_PERCENTAGE else 'FAIL'}",
        fg="yellow",
        bold=True,
    )
    click.secho(
        f"  RECOMPUTED (exact) : {recomputed} = {recomputed_pct}% "
        f"-> {'PASS' if recomputed_pct >= PASS_PERCENTAGE else 'FAIL'}",
        fg="yellow",
        bold=True,
    )
    click.echo(f"  contrast attempt   : {current_user.email} {current_attempt.scores}")

    click.secho("\nURLs:", fg="cyan", bold=True)
    click.secho(
        f"  results page : /courses/{course.slug}/{quiz_index}/complete",
        fg="green",
        bold=True,
    )
    click.echo(f"  quiz item    : /courses/{course.slug}/{quiz_index}/")
    click.echo(f"  topic item   : /courses/{course.slug}/{topic_index}/")

    click.secho(
        "\nCohort (pick this in the admin generate dropdown):", fg="cyan", bold=True
    )
    click.secho(f"  {cohort.name}", fg="green", bold=True)
    click.secho(f"  uuid: {cohort.pk}", fg="green", bold=True)
    click.echo(
        f"  members: {CohortMembership.objects.filter(cohort=cohort, site=site).count()}"
    )
    click.echo(f"  educator panel: /educator/cohorts/{cohort.pk}")
    if educator is not None:
        click.echo(f"  guardian view_cohort granted to {educator.email}")
