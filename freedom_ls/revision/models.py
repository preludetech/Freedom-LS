from __future__ import annotations

from django.conf import settings
from django.db import models

from freedom_ls.site_aware_models.models import SiteAwareModel


class RevisionSchedule(SiteAwareModel):
    """One learner's FSRS state for one question.

    Keyed on the user, not the learner or the course: a person in two
    organisations, or a question whose sections sit in two courses, has one
    memory of the question and so one schedule.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="revision_schedules",
    )
    question = models.ForeignKey(
        "freedom_ls_form_engine.FormQuestion",
        on_delete=models.CASCADE,
        related_name="revision_schedules",
    )
    state = models.PositiveSmallIntegerField()
    step = models.PositiveSmallIntegerField(null=True, blank=True)
    stability = models.FloatField(null=True, blank=True)
    difficulty = models.FloatField(null=True, blank=True)
    # FSRS's next-review time, not a deadline: nothing closes when it passes.
    due = models.DateTimeField()
    last_review = models.DateTimeField(null=True, blank=True)
    reps = models.PositiveIntegerField(default=0)
    lapses = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "question"],
                name="unique_revision_schedule_per_user_question",
            )
        ]
        indexes = [
            models.Index(fields=["user", "due"], name="revision_schedule_user_due_idx")
        ]

    def __str__(self) -> str:
        return f"{self.user} / {self.question_id} due {self.due:%Y-%m-%d %H:%M}"


class RevisionReview(SiteAwareModel):
    """One answer given on the revision page. Append-only, apart from the "I guessed" re-rating."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="revision_reviews",
    )
    question = models.ForeignKey(
        "freedom_ls_form_engine.FormQuestion",
        on_delete=models.CASCADE,
        related_name="revision_reviews",
    )
    # The course whose revision page the answer was given on.
    course = models.ForeignKey(
        "freedom_ls_content_engine.Course",
        on_delete=models.CASCADE,
        related_name="revision_reviews",
    )
    reviewed_at = models.DateTimeField()
    # UUID strings, not a relation: an option without a uuid in its file is
    # re-created on every load, and a relation would lose the choice with it.
    selected_option_ids = models.JSONField(default=list)
    # Stored at answer time so a later edit to an option's `correct` flag never re-marks it.
    was_correct = models.BooleanField()
    guessed = models.BooleanField(default=False)
    rating = models.PositiveSmallIntegerField()
    # The card as it stood before this review, so a re-rating replays from it.
    schedule_before = models.JSONField()

    class Meta:
        indexes = [
            models.Index(
                fields=["user", "question", "-reviewed_at"],
                name="revision_review_latest_idx",
            )
        ]

    def __str__(self) -> str:
        return f"{self.user} / {self.question_id} at {self.reviewed_at:%Y-%m-%d %H:%M}"
