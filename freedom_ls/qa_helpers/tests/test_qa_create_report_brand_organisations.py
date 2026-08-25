"""The brand-organisation command tells QA where a logo lives, so it must be right.

Its whole purpose is to hand QA a file to delete by hand. Reporting a path that
does not exist, or exists=False for a file that is present, sends them hunting
for something that was never there.
"""

from __future__ import annotations

import pytest

from django.core.files.base import ContentFile

from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.qa_helpers.management.commands.qa_create_report_brand_organisations import (
    describe_logo_location,
)

pytestmark = [pytest.mark.fls_internal, pytest.mark.django_db]


@pytest.fixture
def detached_pathless_storage(tmp_path, settings) -> None:
    """A pathless default storage that does NOT live under MEDIA_ROOT.

    The shared pathless_default_storage fixture roots itself at the same
    tmp_path MEDIA_ROOT is isolated to, so a MEDIA_ROOT-relative path resolves
    to the right file there by coincidence. On S3 there is no such coincidence:
    MEDIA_ROOT names nothing the storage knows about. Rooting the storage
    somewhere else is what reproduces that.
    """
    settings.STORAGES = {
        **settings.STORAGES,
        "default": {
            "BACKEND": "freedom_ls.tests.storages.PathlessFileSystemStorage",
            "OPTIONS": {"location": str(tmp_path / "objectstore")},
        },
    }


def test_a_present_logo_is_reported_as_existing_under_pathless_storage(
    mock_site_context, detached_pathless_storage
):
    """Existence has to come from the storage API, not from MEDIA_ROOT.

    Storage.path() raises NotImplementedError by default and S3Storage does not
    override it, so a MEDIA_ROOT-relative path is wrong for any backend that is
    not local disk -- it names a file that is not there and reports the real
    one as missing.
    """
    organisation = OrganisationFactory()
    organisation.logo.save("logo.png", ContentFile(b"not really a png"))

    _, exists = describe_logo_location(organisation)

    assert exists is True


def test_a_pathless_storage_falls_back_to_the_storage_relative_name(
    mock_site_context, detached_pathless_storage
):
    """With no local path to offer, name the object rather than inventing a path."""
    organisation = OrganisationFactory()
    organisation.logo.save("logo.png", ContentFile(b"not really a png"))

    location, _ = describe_logo_location(organisation)

    assert location == organisation.logo.name


def test_a_local_storage_reports_the_real_filesystem_path(mock_site_context):
    """On local disk QA still gets a path they can delete."""
    organisation = OrganisationFactory()
    organisation.logo.save("logo.png", ContentFile(b"not really a png"))

    location, exists = describe_logo_location(organisation)

    assert location == organisation.logo.storage.path(organisation.logo.name)
    assert exists is True


def test_a_deleted_logo_file_is_reported_as_missing(mock_site_context):
    """The state QA creates by hand, which the next run has to notice."""
    organisation = OrganisationFactory()
    organisation.logo.save("logo.png", ContentFile(b"not really a png"))
    organisation.logo.storage.delete(organisation.logo.name)

    _, exists = describe_logo_location(organisation)

    assert exists is False
