"""Re-running the HR attributes seed must find the entries it seeded before."""

from __future__ import annotations

import pytest

from django.contrib.sites.models import Site

from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.hr_attributes"):
    pytest.skip("hr_attributes not installed", allow_module_level=True)

from freedom_ls.hr_attributes.factories import JobTitleFactory
from freedom_ls.hr_attributes.models import JobTitle
from freedom_ls.qa_helpers.management.commands.qa_create_hr_attributes_scenario import (
    _ensure_list,
)

pytestmark = [pytest.mark.fls_internal, pytest.mark.django_db]


def test_an_entry_stored_with_surrounding_spaces_is_reused_not_duplicated(
    mock_site_context: Site,
) -> None:
    """The unique constraint compares trimmed, case-folded names, so the
    lookup has to as well, or the seed tries to create a clashing entry."""
    # Arrange
    organisation = OrganisationFactory()
    existing = JobTitleFactory(organisation=organisation, name=" driver ")

    # Act
    entries = _ensure_list(
        mock_site_context,
        organisation,
        JobTitle,
        JobTitleFactory,
        [("Driver", True)],
    )

    # Assert
    assert entries["Driver"].pk == existing.pk
    assert list(
        JobTitle.objects.filter(organisation=organisation).values_list(
            "name", flat=True
        )
    ) == ["Driver"]
