from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from freedom_ls.form_engine.models import FormStrategy
from freedom_ls.learner_progress.models import FormProgress


def attempt_completes_form(attempt: FormProgress) -> bool:
    """Whether a completed attempt leaves its form finished for progress purposes.

    A learner has to pass to complete: sitting a scored quiz and failing it is an
    attempt, not an item they are done with. A quiz with no pass mark has no bar
    to clear, and neither does a survey, so completing either is enough.
    """
    form = attempt.form
    if form.strategy != FormStrategy.QUIZ or form.quiz_pass_percentage is None:
        return True
    try:
        return attempt.passed()
    except ValueError:
        # An unscored attempt, or a quiz whose questions were added after it was
        # sat, has no percentage to measure against the pass mark.
        return True


def completed_form_ids_by_user(
    user_ids: Iterable[int] | None = None,
) -> dict[int, set[UUID]]:
    """Form ids each learner counts as having finished, keyed by user id.

    Their latest completed attempt decides, matching how the course outline reads
    a quiz's status and how the reports read a learner's score. Pass `user_ids`
    to narrow the scan to the learners you care about.
    """
    attempts = FormProgress.objects.filter(completed_time__isnull=False).select_related(
        "form"
    )
    if user_ids is not None:
        attempts = attempts.filter(user_id__in=user_ids)

    latest_attempts: dict[tuple[int, UUID], FormProgress] = {}
    for attempt in attempts.order_by("completed_time", "start_time"):
        latest_attempts[(attempt.user_id, attempt.form_id)] = attempt

    completed: dict[int, set[UUID]] = {}
    for (user_id, form_id), attempt in latest_attempts.items():
        if attempt_completes_form(attempt):
            completed.setdefault(user_id, set()).add(form_id)
    return completed
