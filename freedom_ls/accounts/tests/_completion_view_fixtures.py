"""Fixture form classes for completion-view & middleware tests.

Stores submitted data in process-local dicts so tests can assert without
needing a project-specific persistence layer.
"""

from __future__ import annotations

from django import forms

# Module-level test storage, reset implicitly between tests via factory_boy
# user pk uniqueness. Tests may assert against these directly.
STORED_PHONE_NUMBERS: dict[int, str] = {}
APPLIES_TO_CALL_COUNT: dict[str, int] = {}
IS_COMPLETE_CALL_COUNT: dict[str, int] = {}


class PhoneNumberForm(forms.Form):
    """Asks for a phone number; stores in `STORED_PHONE_NUMBERS`."""

    phone_number = forms.CharField(max_length=30, required=True)

    @classmethod
    def applies_to(cls, user) -> bool:
        APPLIES_TO_CALL_COUNT[cls.__name__] = (
            APPLIES_TO_CALL_COUNT.get(cls.__name__, 0) + 1
        )
        return not (user.is_superuser or user.is_staff)

    @classmethod
    def is_complete(cls, user) -> bool:
        IS_COMPLETE_CALL_COUNT[cls.__name__] = (
            IS_COMPLETE_CALL_COUNT.get(cls.__name__, 0) + 1
        )
        return user.pk in STORED_PHONE_NUMBERS

    def save(self, user) -> None:
        STORED_PHONE_NUMBERS[user.pk] = self.cleaned_data["phone_number"]


class AlwaysIncompleteForm(forms.Form):
    """Sentinel form that is never complete — used to force middleware
    redirects in middleware tests."""

    @classmethod
    def applies_to(cls, user) -> bool:
        return not user.is_superuser

    @classmethod
    def is_complete(cls, user) -> bool:
        return False

    def save(self, user) -> None:
        pass
