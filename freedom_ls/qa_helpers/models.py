from __future__ import annotations

from django.conf import settings
from django.db import models


class QARegistrationCompletion(models.Model):
    """QA-only marker that a user has completed the additional registration form.

    The shipped in-repo registration forms live in ``accounts/tests`` and track
    completion in a process-local dict, so a ``runserver`` restart re-gates
    everyone. That is fine for unit tests but useless for browser QA, where a
    seeded student must stay "registration-complete" while brand-new signups are
    still gated by ``RegistrationCompletionMiddleware``.

    This DB-backed marker gives durable completion state: a row here means the
    user has satisfied ``QAProfileCompletionForm``. QA infrastructure only —
    kept in ``qa_helpers`` (a dev-only installed app), never in core app code.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="qa_registration_completion",
    )
    how_did_you_hear = models.CharField(max_length=200, blank=True, default="")
    completed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"QA registration complete: user={self.user_id}"
