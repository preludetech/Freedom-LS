"""Form helpers shared by site-aware models."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django import forms

if TYPE_CHECKING:
    # django-stubs does not declare ModelForm's private validation hook, so the
    # type checker is handed a base class that does. At runtime the base is the
    # real ModelForm and super() reaches Django's implementation.
    class _ModelFormBase(forms.ModelForm):
        def _get_validation_exclusions(self) -> set[str]: ...

else:
    _ModelFormBase = forms.ModelForm


class ConstraintValidationFormMixin(_ModelFormBase):
    """Let a ``UniqueConstraint`` reach form validation despite hidden fields.

    Django excludes every field a form does not render from the instance
    validation ``ModelForm._post_clean()`` runs, and
    ``UniqueConstraint.validate()`` abandons the whole constraint as soon as one
    of its fields is in that exclusion set. A constraint spanning a field the
    form never shows is therefore never checked while cleaning, and the
    duplicate row only fails at the database — an ``IntegrityError`` 500 instead
    of a field error the user can act on.

    Subclasses name those fields in ``constraint_fields`` to drop them from the
    exclusion set. Doing so is safe for ``site`` because
    ``SiteAwareModelBase.full_clean()`` fills it from the current request before
    validation runs, so the instance already carries the value the constraint
    looks up. A subclass adding any other field owns the same guarantee for it.

    The exclusion set holds field *names*, which ``UniqueConstraint.validate()``
    compares against the strings in ``fields`` verbatim, and every constraint
    here is spelled ``"site"``, so every one of them needs the help below.
    ``Organisation`` declares ``fields=["site", "name"]`` and ``Cohort`` declares
    ``fields=["site", "organisation", "name"]``; the excluded ``site`` matches
    both, so both forms need this mixin.

    Only name fields whose errors have somewhere to go. Un-excluding a field
    also switches on that field's own model validation, and ``ModelForm`` cannot
    attach an error to a field it does not render. A field left out keeps
    whatever collision handling the model or admin already applies to it — an
    auto-generated ``slug``, say.

    The base is ``ModelForm`` rather than ``object`` so the ``super()`` call
    resolves; subclass it directly, or list it first among a concrete form's
    bases.
    """

    constraint_fields: tuple[str, ...] = ("site",)

    def _get_validation_exclusions(self) -> set[str]:
        return super()._get_validation_exclusions() - set(self.constraint_fields)
