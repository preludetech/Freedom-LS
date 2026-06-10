"""Create a login-ready student with a rich, fully populated dashboard.

Idempotently seeds a single DemoDev student whose dashboard shows all three
sections populated:

- In progress: a course with partial CourseProgress (~43%), no completed_time.
- Completed: a course fully completed (every topic + form done, both quizzes
  passed, CourseProgress at 100% with completed_time set) so the course-finish
  page is reachable.
- Recommended: a RecommendedCourse row.

The completed course is the quiz-ending demo course, so the student also has a
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
from freedom_ls.content_engine.models import Course, Form, Topic
from freedom_ls.student_management.factories import (
    RecommendedCourseFactory,
    UserCourseRegistrationFactory,
)
from freedom_ls.student_management.models import (
    RecommendedCourse,
    UserCourseRegistration,
)
from freedom_ls.student_management.utils import calculate_course_progress_percentage
from freedom_ls.student_progress.models import (
    CourseProgress,
    FormProgress,
    QuestionAnswer,
    TopicProgress,
)

STUDENT_EMAIL = "demodev_s1@email.com"

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


def _get_or_create_student(site: Site) -> User:
    existing: User | None = User.objects.filter(email=STUDENT_EMAIL).first()
    if existing is not None:
        existing.is_active = True
        existing.set_password(STUDENT_EMAIL)
        existing.save(update_fields=["is_active", "password"])
        return existing
    return cast(
        User,
        UserFactory(
            email=STUDENT_EMAIL,
            first_name="DemoDev",
            last_name="Student One",
            is_active=True,
            password=STUDENT_EMAIL,
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
    if not UserCourseRegistration.objects.filter(
        user=user, collection=course, site=site
    ).exists():
        UserCourseRegistrationFactory(user=user, collection=course, site=site)


def _ensure_course_progress_row(user: User, course: Course, site: Site) -> None:
    """Pre-create the CourseProgress row with a site set.

    FormProgress.complete() fires update_course_progress_on_completion, which
    creates CourseProgress WITHOUT a site (NotNullViolation). Owning the row
    first with site=site avoids that.
    """
    CourseProgress.objects.get_or_create(user=user, course=course, site=site)


def _complete_topic(user: User, topic: Topic, site: Site) -> None:
    TopicProgress.objects.get_or_create(
        user=user,
        topic=topic,
        site=site,
        defaults={"complete_time": timezone.now()},
    )


def _attempt_form(
    user: User, form: Form, site: Site, *, all_correct: bool, leave_one_wrong: bool
) -> FormProgress:
    """Create real answers for a form and complete it so it gets a scored attempt.

    For QUIZ forms, answers are picked from the question options. If
    ``leave_one_wrong`` is True, the first question is answered with a wrong
    option (and the rest correct) to demonstrate a passing-but-imperfect score.
    For non-quiz (survey) forms the first option of each question is selected.
    """
    fp: FormProgress
    fp, _ = FormProgress.objects.get_or_create(user=user, form=form, site=site)
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


def _canonical_course_percentage(user: User, course: Course, site: Site) -> int:
    """Compute the course percentage the same way the running app does.

    Mirrors update_course_progress_on_completion: count the user's completed
    topics and forms among the course's viewable items and feed them to the
    canonical calculator, so seeded percentages match runtime behaviour rather
    than a naive completed/total ratio.
    """
    viewable = course.viewable_items()
    completed_topic_ids = set(
        TopicProgress.objects.filter(
            user=user,
            topic__in=[i for i in viewable if isinstance(i, Topic)],
            site=site,
            complete_time__isnull=False,
        ).values_list("topic_id", flat=True)
    )
    completed_form_ids = set(
        FormProgress.objects.filter(
            user=user,
            form__in=[i for i in viewable if isinstance(i, Form)],
            site=site,
            completed_time__isnull=False,
        ).values_list("form_id", flat=True)
    )
    return calculate_course_progress_percentage(
        course, completed_topic_ids, completed_form_ids
    )


def _set_course_progress(
    user: User,
    course: Course,
    site: Site,
    *,
    percentage: int,
    completed: bool,
) -> CourseProgress:
    progress: CourseProgress
    progress, _ = CourseProgress.objects.get_or_create(
        user=user, course=course, site=site
    )
    progress.progress_percentage = percentage
    if completed and progress.completed_time is None:
        progress.completed_time = timezone.now()
    progress.save()
    return progress


@click.command()
@click.argument("site_name", default="DemoDev")
def command(site_name: str) -> None:
    """Seed a login-ready student with a fully populated dashboard.

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

    student = _get_or_create_student(site)
    _ensure_verified_email(student)
    click.secho(
        f"Student: {student.email} (password: {student.email}) site={site.name}",
        fg="green",
    )

    # --- In-progress course: partial progress, no completion ---
    _register(student, in_progress_course, site)
    _ensure_course_progress_row(student, in_progress_course, site)
    items = in_progress_course.viewable_items()
    completed_count = 0
    for item in items[:IN_PROGRESS_ITEMS_TO_COMPLETE]:
        if isinstance(item, Topic):
            _complete_topic(student, item, site)
            completed_count += 1
        elif isinstance(item, Form):
            _attempt_form(student, item, site, all_correct=True, leave_one_wrong=False)
            completed_count += 1
    pct = _canonical_course_percentage(student, in_progress_course, site)
    _set_course_progress(
        student, in_progress_course, site, percentage=pct, completed=False
    )
    click.secho(
        f"In progress: {in_progress_course.slug} "
        f"({completed_count}/{len(items)} items = {pct}%)",
        fg="green",
    )

    # --- Completed course: fully complete, both quizzes passed ---
    _register(student, completed_course, site)
    _ensure_course_progress_row(student, completed_course, site)
    quiz_form: Form | None = None
    quiz_progress: FormProgress | None = None
    for item in completed_course.viewable_items():
        if isinstance(item, Topic):
            _complete_topic(student, item, site)
        elif isinstance(item, Form):
            # 5/6 correct on the 80%-threshold mid-course quiz => PASS, imperfect.
            fp = _attempt_form(
                student,
                item,
                site,
                all_correct=False,
                leave_one_wrong=True,
            )
            if quiz_form is None:
                quiz_form = item
                quiz_progress = fp

    final_pct = _canonical_course_percentage(student, completed_course, site)
    _set_course_progress(
        student, completed_course, site, percentage=final_pct, completed=True
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
        user=student, collection=recommended_course, site=site
    ).exists():
        RecommendedCourseFactory(user=student, collection=recommended_course, site=site)
    click.secho(f"Recommended: {recommended_course.slug}", fg="green")

    click.secho("\n--- Summary ---", fg="cyan", bold=True)
    click.secho(f"Site: {site.name} ({site.domain})", fg="cyan")
    click.secho(f"Login: {student.email} / {student.email}", fg="cyan", bold=True)
    click.secho(f"In progress ({pct}%): {in_progress_course.slug}", fg="cyan")
    click.secho(f"Completed (quiz attempt): {completed_course.slug}", fg="cyan")
    click.secho(f"Recommended: {recommended_course.slug}", fg="cyan")
