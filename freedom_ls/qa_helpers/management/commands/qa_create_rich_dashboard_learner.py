"""Create a login-ready learner with a rich, fully populated dashboard.

Idempotently seeds a single DemoDev learner whose dashboard shows all three
sections populated:

- In progress: a course with partial CourseProgress (~43%), no completed_time.
- Completed: a course fully completed (every topic + form done, both quizzes
  passed, CourseProgress at 100% with completed_time set) so the course-finish
  page is reachable.
- Recommended: a RecommendedCourse row.

The completed course is the quiz-ending demo course, so the learner also has a
genuinely-scored, passing quiz attempt (real QuestionAnswer rows scored via
FormProgress.complete()) for screenshotting quiz feedback.

The login convention in this project is password == email address.
"""

from typing import cast

import djclick as click
from allauth.account.models import EmailAddress

from django.contrib.sites.models import Site
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import ContentCollectionItem, Course, Topic
from freedom_ls.course_recommendations.factories import RecommendedCourseFactory
from freedom_ls.course_recommendations.models import RecommendedCourse
from freedom_ls.form_engine.models import Form, FormProgress, QuestionAnswer
from freedom_ls.learner_management.factories import LearnerCourseRegistrationFactory
from freedom_ls.learner_management.models import LearnerCourseRegistration
from freedom_ls.learner_progress.attempts import ensure_attempt
from freedom_ls.learner_progress.models import CourseProgress, TopicProgress
from freedom_ls.learner_progress.queries import (
    completed_form_item_ids_by_course_progress,
    course_progress_for,
)
from freedom_ls.learner_progress.utils import calculate_course_progress_percentage
from freedom_ls.organisations.utils import get_default_organisation

LEARNER_EMAIL = "demodev_s1@email.com"

IN_PROGRESS_COURSE_SLUG = "functionality-demo-show-end-with-topic"
COMPLETED_COURSE_SLUG = "functionality-demo-show-end-with-quiz"
RECOMMENDED_COURSE_SLUG = "content-widgets-demo-reference"

# Number of leading viewable items to complete in the in-progress course.
IN_PROGRESS_ITEMS_TO_COMPLETE = 3


def _get_course(site: Site, slug: str) -> Course:
    try:
        course: Course = Course.objects.get(slug=slug, site=site)
        return course
    except Course.DoesNotExist as e:
        available = list(
            Course.objects.filter(site=site).values_list("slug", flat=True)
        )
        raise click.ClickException(
            f"Course '{slug}' not found on site '{site.name}'. Available: {available}"
        ) from e


def _get_or_create_learner(site: Site) -> User:
    existing: User | None = User.objects.filter(email=LEARNER_EMAIL).first()
    if existing is not None:
        existing.is_active = True
        existing.set_password(LEARNER_EMAIL)
        existing.save(update_fields=["is_active", "password"])
        return existing
    return cast(
        User,
        UserFactory(
            email=LEARNER_EMAIL,
            first_name="DemoDev",
            last_name="Learner One",
            is_active=True,
            password=LEARNER_EMAIL,
            site=site,
        ),
    )


def _ensure_verified_email(user: User) -> None:
    EmailAddress.objects.update_or_create(
        user=user,
        email=user.email,
        defaults={"verified": True, "primary": True},
    )


def _register(user: User, course: Course, site: Site) -> None:
    if not LearnerCourseRegistration.objects.filter(
        learner__user=user, course=course, site=site
    ).exists():
        LearnerCourseRegistrationFactory(
            learner__user=user,
            learner__organisation=get_default_organisation(site),
            course=course,
            site=site,
        )


def _collection_item_for(course: Course, child: Form | Topic) -> ContentCollectionItem:
    """The collection item placing `child` in `course`."""
    for collection_item in course.viewable_collection_items():
        if collection_item.child == child:
            return collection_item
    raise click.ClickException(
        f"'{child.slug}' is not a viewable item of '{course.slug}'."
    )


def _record_for(user: User, course: Course) -> CourseProgress:
    record = course_progress_for(user, course)
    if record is None:
        raise click.ClickException(
            f"No CourseProgress record for {user.email} on {course.slug}; "
            "register the learner before completing progress."
        )
    return record


def _complete_topic(user: User, course: Course, topic: Topic, site: Site) -> None:
    record = _record_for(user, course)
    collection_item = _collection_item_for(course, topic)
    TopicProgress.objects.get_or_create(
        course_progress=record,
        collection_item=collection_item,
        defaults={"topic": topic, "site": site, "complete_time": timezone.now()},
    )


def _attempt_form(
    user: User,
    course: Course,
    form: Form,
    site: Site,
    *,
    all_correct: bool,
    leave_one_wrong: bool,
) -> FormProgress:
    """Create real answers for a form and complete it so it gets a scored attempt.

    For QUIZ forms, answers are picked from the question options. If
    ``leave_one_wrong`` is True, the first question is answered with a wrong
    option (and the rest correct) to demonstrate a passing-but-imperfect score.
    For non-quiz (survey) forms the first option of each question is selected.
    """
    record = _record_for(user, course)
    collection_item = _collection_item_for(course, form)
    fp: FormProgress = ensure_attempt(record, collection_item)
    if fp.completed_time:
        return fp

    question_index = 0
    for page in form.pages.all():
        for child in page.children():
            if child.content_type != "FORM_QUESTION":
                continue
            question = child
            options = list(question.options.all())
            if not options:
                continue

            chosen = options[0]
            if all_correct or (leave_one_wrong and question_index > 0):
                correct = next((o for o in options if o.correct), None)
                if correct is not None:
                    chosen = correct
            elif leave_one_wrong and question_index == 0:
                wrong = next((o for o in options if not o.correct), None)
                if wrong is not None:
                    chosen = wrong

            answer, _ = QuestionAnswer.objects.get_or_create(
                form_progress=fp, question=question, site=site
            )
            answer.selected_options.set([chosen])
            question_index += 1

    # complete() sets completed_time, scores the form, and saves.
    fp.complete()
    return fp


def _canonical_course_percentage(user: User, course: Course) -> int:
    """Compute the course percentage the same way the running app does.

    Mirrors update_course_progress_on_completion: collect the placements the
    record has finished -- topics from their own rows, forms through the shared
    pass-aware helper -- and feed them to the canonical calculator, so seeded
    percentages match runtime behaviour rather than a naive completed/total
    ratio.
    """
    record = _record_for(user, course)
    viewable_item_ids = [item.id for item in course.viewable_collection_items()]
    completed_item_ids = set(
        TopicProgress.objects.filter(
            course_progress=record,
            collection_item_id__in=viewable_item_ids,
            complete_time__isnull=False,
        ).values_list("collection_item_id", flat=True)
    )
    completed_item_ids |= completed_form_item_ids_by_course_progress([record.pk]).get(
        record.pk, set()
    )
    return calculate_course_progress_percentage(course, completed_item_ids)


def _set_course_progress(
    user: User,
    course: Course,
    *,
    percentage: int,
    completed: bool,
) -> CourseProgress:
    progress = _record_for(user, course)
    progress.progress_percentage = percentage
    if completed and progress.completed_time is None:
        progress.completed_time = timezone.now()
    progress.save()
    return progress


@click.command()
@click.argument("site_name", default="DemoDev")
def command(site_name: str) -> None:
    """Seed a login-ready learner with a fully populated dashboard.

    SITE_NAME is the site to create data on (default: DemoDev).
    """
    try:
        site = Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        available = list(Site.objects.values_list("name", flat=True))
        raise click.ClickException(
            f"Site '{site_name}' not found. Available: {available}"
        ) from e

    in_progress_course = _get_course(site, IN_PROGRESS_COURSE_SLUG)
    completed_course = _get_course(site, COMPLETED_COURSE_SLUG)
    recommended_course = _get_course(site, RECOMMENDED_COURSE_SLUG)

    learner = _get_or_create_learner(site)
    _ensure_verified_email(learner)
    click.secho(
        f"Learner: {learner.email} (password: {learner.email}) site={site.name}",
        fg="green",
    )

    # --- In-progress course: partial progress, no completion ---
    _register(learner, in_progress_course, site)
    items = in_progress_course.viewable_items()
    completed_count = 0
    for item in items[:IN_PROGRESS_ITEMS_TO_COMPLETE]:
        if isinstance(item, Topic):
            _complete_topic(learner, in_progress_course, item, site)
            completed_count += 1
        elif isinstance(item, Form):
            _attempt_form(
                learner,
                in_progress_course,
                item,
                site,
                all_correct=True,
                leave_one_wrong=False,
            )
            completed_count += 1
    pct = _canonical_course_percentage(learner, in_progress_course)
    _set_course_progress(learner, in_progress_course, percentage=pct, completed=False)
    click.secho(
        f"In progress: {in_progress_course.slug} "
        f"({completed_count}/{len(items)} items = {pct}%)",
        fg="green",
    )

    # --- Completed course: fully complete, both quizzes passed ---
    _register(learner, completed_course, site)
    quiz_form: Form | None = None
    quiz_progress: FormProgress | None = None
    for item in completed_course.viewable_items():
        if isinstance(item, Topic):
            _complete_topic(learner, completed_course, item, site)
        elif isinstance(item, Form):
            # 5/6 correct on the 80%-threshold mid-course quiz => PASS, imperfect.
            fp = _attempt_form(
                learner,
                completed_course,
                item,
                site,
                all_correct=False,
                leave_one_wrong=True,
            )
            if quiz_form is None:
                quiz_form = item
                quiz_progress = fp

    final_pct = _canonical_course_percentage(learner, completed_course)
    _set_course_progress(
        learner, completed_course, percentage=final_pct, completed=True
    )
    if quiz_form is not None and quiz_progress is not None:
        scores = quiz_progress.scores or {}
        pct_score = quiz_progress.quiz_percentage()
        outcome = "PASS" if quiz_progress.passed() else "FAIL"
        click.secho(
            f"Completed: {completed_course.slug} (100%, completed_time set). "
            f"Quiz '{quiz_form.slug}' score={scores.get('score')}/"
            f"{scores.get('max_score')} = {pct_score}% -> {outcome}",
            fg="green",
        )

    # --- Recommended course ---
    if not RecommendedCourse.objects.filter(
        user=learner, course=recommended_course, site=site
    ).exists():
        RecommendedCourseFactory(user=learner, course=recommended_course, site=site)
    click.secho(f"Recommended: {recommended_course.slug}", fg="green")

    click.secho("\n--- Summary ---", fg="cyan", bold=True)
    click.secho(f"Site: {site.name} ({site.domain})", fg="cyan")
    click.secho(f"Login: {learner.email} / {learner.email}", fg="cyan", bold=True)
    click.secho(f"In progress ({pct}%): {in_progress_course.slug}", fg="cyan")
    click.secho(f"Completed (quiz attempt): {completed_course.slug}", fg="cyan")
    click.secho(f"Recommended: {recommended_course.slug}", fg="cyan")
