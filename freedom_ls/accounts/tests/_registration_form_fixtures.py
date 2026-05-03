"""Fixture form classes for `test_registration_forms.py`.

Lives in a real module path (``freedom_ls.accounts.tests._registration_form_fixtures``)
so that ``import_string`` resolves the same class objects as direct imports
in the test file.
"""

from __future__ import annotations

from django import forms


class GoodForm(forms.Form):
    """A protocol-compliant form."""

    name = forms.CharField(max_length=100)

    @classmethod
    def applies_to(cls, user) -> bool:
        return True

    @classmethod
    def is_complete(cls, user) -> bool:
        return False

    def save(self, user) -> None:
        pass


class CompleteForm(forms.Form):
    """A form whose ``is_complete`` returns True."""

    @classmethod
    def applies_to(cls, user) -> bool:
        return True

    @classmethod
    def is_complete(cls, user) -> bool:
        return True

    def save(self, user) -> None:
        pass


class DoesNotApplyForm(forms.Form):
    """A form whose ``applies_to`` returns False."""

    @classmethod
    def applies_to(cls, user) -> bool:
        return False

    @classmethod
    def is_complete(cls, user) -> bool:  # pragma: no cover — must not be called
        raise RuntimeError("is_complete should not be reached")

    def save(self, user) -> None:
        pass


class RaisesInAppliesToForm(forms.Form):
    """A form whose ``applies_to`` raises."""

    @classmethod
    def applies_to(cls, user) -> bool:
        raise RuntimeError("boom in applies_to")

    @classmethod
    def is_complete(cls, user) -> bool:  # pragma: no cover — must not be called
        raise RuntimeError("is_complete should not be reached")

    def save(self, user) -> None:  # pragma: no cover — must not be called
        pass


class RaisesInIsCompleteForm(forms.Form):
    """A form whose ``is_complete`` raises."""

    @classmethod
    def applies_to(cls, user) -> bool:
        return True

    @classmethod
    def is_complete(cls, user) -> bool:
        raise RuntimeError("boom in is_complete")

    def save(self, user) -> None:  # pragma: no cover — must not be called
        pass


class NotAFormClass:
    """Not a forms.Form subclass."""


class ForbiddenFieldForm(forms.Form):
    """A form that includes a forbidden user-identifying field."""

    user_id = forms.IntegerField()

    @classmethod
    def applies_to(cls, user) -> bool:
        return True

    @classmethod
    def is_complete(cls, user) -> bool:
        return False

    def save(self, user) -> None:
        pass
