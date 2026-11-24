"""Create (or reset) three learners for QA of the quiz declaration.

Works on the demo course ``functionality-demo-quiz-declaration`` (load it with
``manage.py content_save demo_content DemoDev``), whose items are a topic, a
quiz with its own declaration text and a quiz with the site's default text.
Every learner is active, has a verified primary email and is registered
individually on the course:

* **A** (``--email-a``) is also registered on every ``--extra-course-slug``
  and holds no ``FormProgress`` at any form in those courses. The topics ahead
  of each course's first form are complete, so that form's start screen is
  reachable and offers "Start Form" (a quiz after another quiz stays locked
  until the one before it is passed).
* **B** (``--email-b``) has the topic complete and one open sitting at the quiz
  with its own declaration, with no ``FormDeclaration`` and no answers: a
  sitting begun before the author turned the declaration on.
* **C** (``--email-c``) has the topic complete, a passed and signed sitting at
  the first quiz (so the second is reachable), and a completed, failed, signed
  sitting at the quiz with the default declaration: its start screen offers
  "Try Again".

Signed sittings go through ``start_attempt`` with a declaration, as the
declaration view does, so the declaration is the effective text and is signed
between the sitting's start and its completion.

Re-running resets each learner: their ``FormProgress`` rows at the forms in
scope are printed and deleted (``FormDeclaration``, ``CourseFormAttempt`` and
answers cascade with them) before the state above is rebuilt.

Usage:
    uv run python manage.py qa_create_quiz_declaration_scenario
    uv run python manage.py qa_create_quiz_declaration_scenario DemoDev \
        --extra-course-slug functionality-demo-shuffled-quiz
"""

from typing import cast

import djclick as click

from django.contrib.sites.models import Site
from django.http import QueryDict

from freedom_ls.content_engine.models import ContentCollectionItem, Course, Topic
from freedom_ls.form_engine.enums import OPTION_QUESTION_TYPES
from freedom_ls.form_engine.models import Form, FormDeclaration, FormProgress
from freedom_ls.form_engine.queries import form_questions, quiz_verdict
from freedom_ls.learner_progress.attempts import get_or_create_incomplete, start_attempt
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.qa_helpers.management.commands.qa_create_dashboard_paging_fixtures import (
    _get_course,
    _get_site,
    _register,
)
from freedom_ls.qa_helpers.management.commands.qa_create_fresh_course_learners import (
    DEV_PASSWORD,
    _clear_form_progress,
    _course_forms,
    _ensure_user,
)
from freedom_ls.qa_helpers.management.commands.qa_set_item_completion import (
    _complete_topic,
    _items,
)

COURSE_SLUG = "functionality-demo-quiz-declaration"
TOPIC_TITLE = "The Sun and the Moon"
OWN_DECLARATION_QUIZ = "Quiz with its own declaration"
DEFAULT_DECLARATION_QUIZ = "Quiz with the default declaration"
SIGNING_IP = "127.0.0.1"


def _answer(sitting: FormProgress, *, correctly: bool) -> None:
    """Answer every choice question with its correct options, or with one wrong one."""
    questions = [
        question
        for question in form_questions(sitting.form)
        if question.type in OPTION_QUESTION_TYPES
    ]
    post_data = QueryDict(mutable=True)
    for question in questions:
        options = question.options.filter(correct=True)
        if not correctly:
            options = question.options.exclude(correct=True)[:1]
        post_data.setlist(f"question_{question.id}", [str(o.pk) for o in options])
    rejected = sitting.save_answers(questions, post_data)
    if rejected:
        raise click.ClickException(f"Answers rejected: {list(rejected)}")


def _signed_sitting(
    record: CourseProgress, item: ContentCollectionItem, typed_name: str
) -> FormProgress:
    """A sitting begun the way the declaration view begins one: signed first."""
    form = cast(Form, item.child)
    declaration = FormDeclaration(
        declaration_text=form.effective_declaration_text(),
        typed_name=typed_name,
        ip_address=SIGNING_IP,
    )
    return start_attempt(record, item, declaration=declaration)


def _completed_signed_sitting(
    record: CourseProgress,
    item: ContentCollectionItem,
    typed_name: str,
    *,
    passed: bool,
) -> FormProgress:
    sitting = _signed_sitting(record, item, typed_name)
    _answer(sitting, correctly=passed)
    sitting.complete()
    sitting.refresh_from_db()
    verdict = quiz_verdict(sitting.form, sitting)
    if verdict is not passed:
        raise click.ClickException(
            f"Sitting {sitting.pk} at '{sitting.form.slug}' has verdict {verdict}, "
            f"expected {passed}."
        )
    return sitting


def _describe(sitting: FormProgress) -> str:
    declaration = FormDeclaration.objects.filter(form_progress=sitting).first()
    signed = (
        f"signed by '{declaration.typed_name}' at {declaration.signed_at:%H:%M:%S}"
        if declaration
        else "UNSIGNED"
    )
    state = (
        f"completed, scores={sitting.scores}, "
        f"passed={quiz_verdict(sitting.form, sitting)}"
        if sitting.completed_time
        else f"OPEN, answers={sitting.answers.count()}"
    )
    return f"FormProgress {sitting.pk} at '{sitting.form.slug}': {state}, {signed}"


def _complete_leading_topics(site: Site, record: CourseProgress) -> None:
    """Complete the topics placed before the course's first form, which unlocks it."""
    for item in record.course.viewable_collection_items():
        if not isinstance(item.child, Topic):
            return
        _complete_topic(site, record, item)


def _learner(
    site: Site, email: str, password: str, courses: list[Course], label: str
) -> list[CourseProgress]:
    """The learner, registered on ``courses``, with no sittings at their forms.

    Returns the record for each course, in order.
    """
    user = _ensure_user(site, email, password)
    click.secho(f"\nLearner {label}: {email} (pk {user.pk})", fg="green", bold=True)
    records = [_register(user, course, site) for course in courses]
    for course in courses:
        click.echo(f"  registered on {course.title} ({course.slug})")
    _clear_form_progress(user, _course_forms(courses))
    return records


@click.command()
@click.argument("site_name", default="DemoDev")
@click.option("--email-a", default="qa-decl-a@example.com", show_default=True)
@click.option("--email-b", default="qa-decl-b@example.com", show_default=True)
@click.option("--email-c", default="qa-decl-c@example.com", show_default=True)
@click.option(
    "--extra-course-slug",
    "extra_course_slugs",
    multiple=True,
    default=("functionality-demo-shuffled-quiz",),
    show_default=True,
    help="Repeatable. Further courses learner A is registered on.",
)
@click.option("--password", default=DEV_PASSWORD, show_default=True)
def command(
    site_name: str,
    email_a: str,
    email_b: str,
    email_c: str,
    extra_course_slugs: tuple[str, ...],
    password: str,
) -> None:
    """Create or reset learners A, B and C for quiz declaration QA."""
    site = _get_site(site_name)
    course = _get_course(site, COURSE_SLUG)
    extra_courses = [_get_course(site, slug) for slug in extra_course_slugs]
    topic_item, own_item, default_item = _items(
        course, (TOPIC_TITLE, OWN_DECLARATION_QUIZ, DEFAULT_DECLARATION_QUIZ)
    )
    click.secho(f"Site: {site.name} ({site.domain})", fg="cyan", bold=True)

    for record_a in _learner(site, email_a, password, [course, *extra_courses], "A"):
        _complete_leading_topics(site, record_a)

    [record_b] = _learner(site, email_b, password, [course], "B")
    _complete_topic(site, record_b, topic_item)
    open_sitting = get_or_create_incomplete(record_b, own_item)
    click.echo(f"  {_describe(open_sitting)}")

    [record_c] = _learner(site, email_c, password, [course], "C")
    _complete_topic(site, record_c, topic_item)
    passed = _completed_signed_sitting(record_c, own_item, "QA Decl C", passed=True)
    click.echo(f"  {_describe(passed)}")
    failed = _completed_signed_sitting(
        record_c, default_item, "QA Decl C", passed=False
    )
    click.echo(f"  {_describe(failed)}")

    items = list(course.viewable_collection_items())
    click.secho("\nStart screens:", fg="cyan", bold=True)
    for item in (own_item, default_item):
        index = items.index(item) + 1
        click.echo(f"  {cast(Form, item.child).title}: /courses/{course.slug}/{index}/")
