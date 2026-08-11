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


class SiteScopedConstraintFormMixin(_ModelFormBase):
    """Let site-scoped ``UniqueConstraint``s reach form validation.

    Site-aware admin forms hide ``site``, so Django puts it in
    ``ModelForm._get_validation_exclusions()``. ``UniqueConstraint.validate()``
    bails out as soon as one of its fields is excluded, so a constraint spanning
    ``("site", "name")`` is never checked while the form is cleaning and the
    duplicate row only fails at the database — an ``IntegrityError`` 500 instead
    of a field error the user can act on.

    Dropping the site-side fields from the exclusion set restores the check.
    That is safe because ``SiteAwareModelBase.full_clean()`` fills ``site`` from
    the current request before validation runs, so the instance already carries
    the value the constraint looks up.

    Subclasses set ``constraint_fields`` to the hidden fields their constraints
    span. Anything left out stays excluded, so a constraint covering a field the
    form never sees — an auto-generated ``slug``, say — keeps whatever collision
    handling the model or admin already applies to it.

    The base is ``ModelForm`` rather than ``object`` so the ``super()`` call
    resolves; subclass it directly, or list it first among a concrete form's
    bases.
    """

    constraint_fields: tuple[str, ...] = ("site",)

    def _get_validation_exclusions(self) -> set[str]:
        return super()._get_validation_exclusions() - set(self.constraint_fields)
