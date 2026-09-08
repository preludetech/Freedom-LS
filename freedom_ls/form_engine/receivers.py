"""Signal receivers for the form_engine app.

Connected by `FormEngineConfig.ready()`. A receiver in a module nothing imports
is never connected, and fails silently rather than loudly.
"""

from __future__ import annotations

from django.db.models.signals import post_delete
from django.dispatch import receiver

from freedom_ls.form_engine.models import QuestionAnswerFile


@receiver(post_delete, sender=QuestionAnswerFile)
def delete_question_answer_file(
    sender: type[QuestionAnswerFile], instance: QuestionAnswerFile, **kwargs: object
) -> None:
    """Storage does not follow the row. An orphaned scan of someone's ID is PII
    left in a bucket with nothing naming it.
    """
    if not instance.file:
        return
    instance.file.delete(save=False)
