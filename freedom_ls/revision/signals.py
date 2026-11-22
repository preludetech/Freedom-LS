"""Receivers that keep revision rows in step with form_engine."""

from uuid import UUID

from django.dispatch import receiver

from freedom_ls.form_engine.models import FormQuestion
from freedom_ls.form_engine.signals import form_questions_dropped
from freedom_ls.revision.models import RevisionReview, RevisionSchedule


@receiver(form_questions_dropped, sender=FormQuestion)
def delete_revision_rows_of_dropped_questions(
    sender: type[FormQuestion], question_ids: list[UUID], **kwargs: object
) -> None:
    """Delete the schedules and reviews of questions their files no longer hold.

    The question rows stay: quiz answers protect them.
    """
    # The receiver runs from the content load, where no request sets a current
    # site, and a question id belongs to one site, so the id filter is the
    # site scope.
    RevisionSchedule._base_manager.filter(question_id__in=question_ids).delete()
    RevisionReview._base_manager.filter(question_id__in=question_ids).delete()
