from __future__ import annotations

from django.db import models


class MessagingFlag(models.TextChoices):
    INHERIT = "inherit"
    OPEN = "open"
    CLOSED = "closed"


FLAG_NAMES: tuple[str, ...] = (
    "learner_to_educator",
    "learner_to_cohort_peer",
    "learner_to_course_peer",
)
