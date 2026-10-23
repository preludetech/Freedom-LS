"""The one definition of a learner's progress status, shared by every surface."""

from __future__ import annotations

from django.db.models import TextChoices


class ProgressStatus(TextChoices):
    NOT_STARTED = "not_started", "Not started"
    IN_PROGRESS = "in_progress", "In progress"
    COMPLETE = "complete", "Complete"


def progress_status(completion_percentage: int) -> ProgressStatus:
    """The status a recomputed completion percentage falls in.

    1 to 99 is in progress, so a learner is never "not started" once they have
    completed anything and never "complete" before every item is done.
    """
    if completion_percentage <= 0:
        return ProgressStatus.NOT_STARTED
    if completion_percentage >= 100:
        return ProgressStatus.COMPLETE
    return ProgressStatus.IN_PROGRESS
