"""ConstraintValidationFormMixin: keeping site-scoped constraints checkable.

SiteAwareModelAdmin renders no `site` field, and Django excludes every
unrendered field from the instance validation `_post_clean()` runs.
`UniqueConstraint.validate()` then abandons any constraint mentioning an
excluded field, so a duplicate reaches the database as an IntegrityError 500
rather than a form error. The mixin's whole job is one set subtraction.
"""

from __future__ import annotations

import pytest

from django import forms

from freedom_ls.learner_management.models import Cohort
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.site_aware_models.forms import ConstraintValidationFormMixin

pytestmark = pytest.mark.django_db


class _CohortFormWithoutSite(ConstraintValidationFormMixin):
    class Meta:
        model = Cohort
        fields = ("organisation", "name")


class _PlainCohortForm(forms.ModelForm):
    class Meta:
        model = Cohort
        fields = ("organisation", "name")


def _cleaned(form_class, mock_site_context):
    """A bound, cleaned form -- exclusions are only computed during cleaning."""
    form = form_class(
        data={"organisation": OrganisationFactory().pk, "name": "Year 10 Science"}
    )
    form.is_valid()
    return form


def test_django_excludes_the_unrendered_site_field_from_validation(
    mock_site_context,
) -> None:
    """The behaviour the mixin exists to correct."""
    form = _cleaned(_PlainCohortForm, mock_site_context)

    assert "site" in form._get_validation_exclusions()


def test_the_mixin_un_excludes_the_named_constraint_fields(mock_site_context) -> None:
    form = _cleaned(_CohortFormWithoutSite, mock_site_context)

    assert "site" not in form._get_validation_exclusions()


def test_fields_the_subclass_does_not_name_stay_excluded(mock_site_context) -> None:
    """Un-excluding switches on that field's own validation, so it is opt-in."""
    form = _cleaned(_CohortFormWithoutSite, mock_site_context)

    assert "created_at" in form._get_validation_exclusions()
