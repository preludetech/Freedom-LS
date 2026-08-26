"""Every FileSystemStorage-backed alias must follow MEDIA_ROOT into the
per-test tmp dir, never the working tree's real media/ directory.

_isolate_media_root (freedom_ls/conftest.py) redirects MEDIA_ROOT for every
test, and each alias in settings.STORAGES tracks MEDIA_ROOT because it
declares no OPTIONS["location"]. These tests exercise the three model
fields that actually write through that mechanism.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from django.core.files.base import ContentFile

from config.settings_base import MEDIA_ROOT as WORKING_TREE_MEDIA_ROOT
from freedom_ls.content_engine.factories import FileFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.reports.factories import GeneratedReportFactory


@pytest.mark.django_db
def test_content_engine_file_saves_under_tmp_media_root(
    tmp_path: Path, mock_site_context: object
) -> None:
    file_obj = FileFactory()

    saved_path = Path(file_obj.file.path)

    assert saved_path.is_relative_to(tmp_path)
    assert not saved_path.is_relative_to(WORKING_TREE_MEDIA_ROOT)


@pytest.mark.django_db
def test_organisation_logo_saves_under_tmp_media_root(
    tmp_path: Path, mock_site_context: object
) -> None:
    organisation = OrganisationFactory()
    organisation.logo.save("logo.png", ContentFile(b"fake-logo-bytes"), save=True)

    saved_path = Path(organisation.logo.path)

    assert saved_path.is_relative_to(tmp_path)
    assert not saved_path.is_relative_to(WORKING_TREE_MEDIA_ROOT)


@pytest.mark.django_db
def test_generated_report_file_saves_under_tmp_media_root(
    tmp_path: Path, mock_site_context: object
) -> None:
    report = GeneratedReportFactory()
    report.file.save("cohort-report.pdf", ContentFile(b"%PDF-1.4"), save=True)

    saved_path = Path(report.file.path)

    assert saved_path.is_relative_to(tmp_path)
    assert not saved_path.is_relative_to(WORKING_TREE_MEDIA_ROOT)


@pytest.mark.django_db
def test_organisation_logo_name_starts_with_organisations_prefix(
    mock_site_context: object,
) -> None:
    organisation = OrganisationFactory()
    organisation.logo.save("logo.png", ContentFile(b"fake-logo-bytes"), save=True)

    assert organisation.logo.name.startswith("organisations/")


@pytest.mark.django_db
def test_generated_report_file_name_starts_with_cohort_reports_prefix(
    mock_site_context: object,
) -> None:
    report = GeneratedReportFactory()
    report.file.save("cohort-report.pdf", ContentFile(b"%PDF-1.4"), save=True)

    assert report.file.name.startswith("cohort_reports/")
