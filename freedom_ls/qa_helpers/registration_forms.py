"""A DB-backed additional-registration form for browser QA.

Wired into a site via ``SiteSignupPolicy.additional_registration_forms`` (dotted
path ``freedom_ls.qa_helpers.registration_forms.QAProfileCompletionForm``) it
lets QA exercise ``RegistrationCompletionMiddleware`` (Workflow 7): a brand-new
signup is intercepted and routed to the "Complete your registration" page until
they submit this form, while a seeded student pre-marked via
``QARegistrationCompletion`` is treated as complete and passes straight through.

Satisfies ``RegistrationFormProtocol`` (``applies_to`` / ``is_complete`` /
``save``). Completion is persisted in the DB (unlike the ``accounts/tests``
fixtures) so it survives a ``runserver`` restart.
"""

from __future__ import annotations

from django import forms

from freedom_ls.accounts.models import User

from .models import QARegistrationCompletion


class QAProfileCompletionForm(forms.Form):
    """Collect one extra detail after signup; store it durably in the DB."""

    how_did_you_hear = forms.CharField(
        max_length=200,
        required=True,
        label="How did you hear about us?",
    )

    @classmethod
    def applies_to(cls, user: User) -> bool:
        # Staff/superusers are never gated (mirrors the shipped fixtures and the
        # middleware's own superuser short-circuit).
        return not (user.is_superuser or user.is_staff)

    @classmethod
    def is_complete(cls, user: User) -> bool:
        return QARegistrationCompletion.objects.filter(user=user).exists()

    def save(self, user: User) -> None:
        QARegistrationCompletion.objects.update_or_create(
            user=user,
            defaults={"how_did_you_hear": self.cleaned_data["how_did_you_hear"]},
        )
