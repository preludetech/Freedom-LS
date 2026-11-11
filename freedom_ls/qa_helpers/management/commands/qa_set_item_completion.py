"""Complete, or undo the completion of, named course items for one learner.

Works on the record the learner interface writes to (``course_progress_for``), so a
learner with both a cohort and an individual registration gets the one the player uses.

* ``--action complete``: a topic gets a ``TopicProgress`` with ``complete_time`` now; a
  form gets its open course attempt answered with every correct option (so a quiz is
  passed) and completed through ``FormProgress.complete()`` (so it is scored as a real
  submission), or a new attempt built and completed when none is open.
* ``--action undo``: deletes the learner's ``TopicProgress`` rows for a topic, or every
  ``FormProgress`` sitting (open or completed, cascading to its ``CourseFormAttempt``) for
  a form, at that placement, printing each row first. The record's percentage is
  recalculated, and its course ``completed_time`` cleared when it drops below 100%.

``--finish-course`` (with ``complete``) then stamps the record's course ``completed_time``
when ``outstanding_items`` is empty, as the course finish page does, but without firing
the ``course.completed`` webhook.

Items are matched by title among the course's viewable items (parts flattened).

Usage:
    uv run python manage.py qa_set_item_completion \\
        --learner qa_deadline_fresh@email.com \\
        --course-slug functionality-demo-course-parts \\
        --item "Welcome" --item "Knowledge Check" --action complete
    ... --action undo
"""

from typing import cast

import djclick as click

from django.contrib.sites.models import Site
from django.http import QueryDict
from django.utils import timezone

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import ContentCollectionItem, Course, Topic
from freedom_ls.form_engine.enums import OPTION_QUESTION_TYPES
from freedom_ls.form_engine.models import Form, FormProgress
from freedom_ls.form_engine.queries import form_questions
from freedom_ls.learner_interface.utils import outstanding_items
from freedom_ls.learner_progress.factories import CourseFormAttemptFactory
from freedom_ls.learner_progress.models import (
    CourseFormAttempt,
    CourseProgress,
    TopicProgress,
)
from freedom_ls.learner_progress.queries import course_progress_for
from freedom_ls.learner_progress.signals import recalculate_progress_percentage

COMPLETE = "complete"
UNDO = "undo"


def _get_site(site_name: str) -> Site:
    try:
        return Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        available = list(Site.objects.values_list("name", flat=True))
        raise click.ClickException(
            f"Site '{site_name}' not found. Available: {available}"
        ) from e


def _items(course: Course, titles: tuple[str, ...]) -> list[ContentCollectionItem]:
    by_title = {
        str(getattr(item.child, "title", "")): item
        for item in course.viewable_collection_items()
    }
    missing = [title for title in titles if title not in by_title]
    if missing:
        raise click.ClickException(
            f"{course.slug} has no item(s) {missing}. Items: {list(by_title)}"
        )
    return [by_title[title] for title in titles]


def _complete_topic(
    site: Site, record: CourseProgress, item: ContentCollectionItem
) -> None:
    progress, created = TopicProgress._base_manager.get_or_create(
        course_progress=record,
        collection_item=item,
        defaults={"site": site, "topic": cast(Topic, item.child)},
    )
    if progress.complete_time is None:
        progress.complete_time = timezone.now()
        # save() fires the signal that recalculates the record's percentage.
        progress.save()
    click.echo(
        f"  TopicProgress {progress.pk} complete_time {progress.complete_time}"
        f"{' (created)' if created else ''}"
    )


def _answer_correctly(sitting: FormProgress) -> None:
    """Select every correct option on the form's choice questions, so a quiz with a pass
    mark is passed (a failed quiz does not complete its placement)."""
    questions = [
        question
        for question in form_questions(sitting.form)
        if question.type in OPTION_QUESTION_TYPES
    ]
    post_data = QueryDict(mutable=True)
    for question in questions:
        post_data.setlist(
            f"question_{question.id}",
            [str(option.pk) for option in question.options.filter(correct=True)],
        )
    rejected = sitting.save_answers(questions, post_data)
    click.echo(
        f"  Answered {len(questions)} choice question(s) correctly"
        f"{f'; rejected {list(rejected)}' if rejected else ''}"
    )


def _complete_form(
    site: Site, record: CourseProgress, item: ContentCollectionItem
) -> None:
    attempt = (
        CourseFormAttempt._base_manager.filter(
            course_progress=record,
            collection_item=item,
            form_progress__completed_time__isnull=True,
        )
        .select_related("form_progress")
        .first()
    )
    if attempt is None:
        attempt = cast(
            CourseFormAttempt,
            CourseFormAttemptFactory(
                site=site,
                course_progress=record,
                form=cast(Form, item.child),
                collection_item=item,
            ),
        )
        click.echo(f"  Built attempt {attempt.pk}")
    sitting: FormProgress = attempt.form_progress
    _answer_correctly(sitting)
    # complete() scores the sitting and fires the signal that moves the percentage.
    sitting.complete()
    click.echo(
        f"  FormProgress {sitting.pk} completed {sitting.completed_time} "
        f"scores {sitting.scores}"
    )


def _undo(record: CourseProgress, item: ContentCollectionItem) -> None:
    if isinstance(item.child, Form):
        sittings = FormProgress._base_manager.filter(
            course_attempt__course_progress=record,
            course_attempt__collection_item=item,
        )
        for sitting in sittings:
            click.echo(
                f"  Removing FormProgress {sitting.pk} [{sitting.site_id}] completed "
                f"{sitting.completed_time}"
            )
        click.echo(f"  Removed: {sittings.delete()}")
        return
    progress_rows = TopicProgress._base_manager.filter(
        course_progress=record, collection_item=item
    )
    for progress in progress_rows:
        click.echo(
            f"  Removing TopicProgress {progress.pk} complete_time {progress.complete_time}"
        )
    click.echo(f"  Removed: {progress_rows.delete()}")


@click.command()
@click.option("--learner", "email", required=True, help="Learner email.")
@click.option("--course-slug", required=True, help="Course slug.")
@click.option(
    "--item", "titles", multiple=True, required=True, help="Item title (repeatable)."
)
@click.option("--action", type=click.Choice([COMPLETE, UNDO]), required=True)
@click.option(
    "--finish-course",
    is_flag=True,
    default=False,
    help="After completing, stamp the course completed_time if nothing is outstanding "
    "(as the finish page does, without its webhook).",
)
@click.option("--site-name", default="DemoDev", help="Site the course lives on.")
def command(
    email: str,
    course_slug: str,
    titles: tuple[str, ...],
    action: str,
    finish_course: bool,
    site_name: str,
) -> None:
    """Complete or undo named items of COURSE_SLUG for one learner."""
    site = _get_site(site_name)
    user = User._base_manager.filter(email=email).first()
    if user is None:
        raise click.ClickException(f"No user with email '{email}'.")
    course = Course._base_manager.filter(site=site, slug=course_slug).first()
    if course is None:
        raise click.ClickException(f"Course '{course_slug}' not on '{site_name}'.")
    record = course_progress_for(user, course)
    if record is None:
        raise click.ClickException(f"{email} has no live record for {course_slug}.")
    click.echo(f"Record {record.pk} ({email} / {course_slug}) on {site.name}")

    for item in _items(course, titles):
        click.secho(
            f"{action}: {getattr(item.child, 'title', '')!r} (placement {item.pk})",
            fg="cyan",
        )
        if action == UNDO:
            _undo(record, item)
        elif isinstance(item.child, Form):
            _complete_form(site, record, item)
        else:
            _complete_topic(site, record, item)

    recalculate_progress_percentage(record)
    if record.progress_percentage < 100 and record.completed_time is not None:
        click.echo(f"Clearing course completed_time {record.completed_time}")
        record.completed_time = None
        record.save(update_fields=["completed_time"])
    if finish_course and action == COMPLETE and record.completed_time is None:
        still_to_do = outstanding_items(record, course)
        if still_to_do:
            click.secho(f"Not finished; outstanding: {still_to_do}", fg="yellow")
        else:
            record.completed_time = timezone.now()
            record.save(update_fields=["completed_time"])
    click.secho(
        f"Record {record.pk} now {record.progress_percentage}%, "
        f"completed_time {record.completed_time}",
        fg="green",
    )
