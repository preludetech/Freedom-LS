"""Tests for the content_engine admin forms."""

from __future__ import annotations

import pytest

from django.core.exceptions import NON_FIELD_ERRORS
from django.core.files.uploadedfile import SimpleUploadedFile

from freedom_ls.content_engine.factories import FileFactory
from freedom_ls.content_engine.forms import FileAdminForm

# Regression test for FileAdminForm.
#
# SiteAwareModelAdmin excludes ``site`` from every admin form, and
# UniqueConstraint.validate() abandons a constraint whose field sits in that
# exclusion set. FileAdminForm un-excludes ``site`` so a duplicate file path
# surfaces as an error on the File path field instead of an IntegrityError.


@pytest.mark.django_db
def test_file_admin_form_rejects_duplicate_file_path(mock_site_context):
    existing = FileFactory(file_path="content/duplicate.txt")

    form = FileAdminForm(
        data={
            "file_type": existing.file_type,
            "file_path": "content/duplicate.txt",
            "original_filename": "duplicate.txt",
        },
        files={"file": SimpleUploadedFile("duplicate.txt", b"content")},
    )

    assert form.is_valid() is False
    assert "file_path" in form.errors
    assert NON_FIELD_ERRORS not in form.errors
