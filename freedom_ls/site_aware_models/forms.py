"""Form helpers shared by site-aware models."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django import forms
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.db import router
from django.db.models import BaseConstraint, UniqueConstraint

if TYPE_CHECKING:
    # django-stubs does not declare ModelForm's private validation hook, so the
    # type checker is handed a base class that does. At runtime the base is the
    # real ModelForm and super() reaches Django's implementation.
    class _ModelFormBase(forms.ModelForm):
        def _get_validation_exclusions(self) -> set[str]: ...
        def _update_errors(self, errors: ValidationError) -> None: ...

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

    Django only keys a uniqueness error to a field when the constraint has one
    field, so a ``(site, organisation, name)`` clash would otherwise surface as
    a form-level error. When exactly one of a constraint's fields is rendered,
    that field is the only one the user can change, so the error goes on it
    and the input is marked invalid. With two or more rendered there is no
    single field to blame, and the error stays form-level.

    The base is ``ModelForm`` rather than ``object`` so the ``super()`` call
    resolves; subclass it directly, or list it first among a concrete form's
    bases.
    """

    constraint_fields: tuple[str, ...] = ("site",)

    def _get_validation_exclusions(self) -> set[str]:
        return super()._get_validation_exclusions() - set(self.constraint_fields)

    def validate_constraints(self) -> None:
        instance = self.instance
        exclude = self._get_validation_exclusions()
        using = router.db_for_write(type(instance), instance=instance)
        for model_class, constraints in instance.get_constraints():
            for constraint in constraints:
                try:
                    constraint.validate(
                        model_class, instance, exclude=exclude, using=using
                    )
                except ValidationError as error:
                    self._update_errors(
                        ValidationError({self._error_key(constraint): error})
                    )

    def _error_key(self, constraint: BaseConstraint) -> str:
        """The one rendered field a unique constraint spans, else form-level."""
        if not isinstance(constraint, UniqueConstraint):
            return NON_FIELD_ERRORS
        rendered = [name for name in constraint.fields if name in self.fields]
        return rendered[0] if len(rendered) == 1 else NON_FIELD_ERRORS
