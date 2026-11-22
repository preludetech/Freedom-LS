"""Tests for the ContentSave and ContentSaveSource models."""

import pytest

from django.db import IntegrityError, transaction
from django.db.models import ProtectedError

from freedom_ls.content_engine.factories import (
    ContentSaveFactory,
    ContentSaveSourceFactory,
)


@pytest.mark.django_db
def test_two_sources_of_one_save_cannot_share_an_order(mock_site_context):
    content_save = ContentSaveFactory()
    ContentSaveSourceFactory(content_save=content_save, order=0)

    with pytest.raises(IntegrityError), transaction.atomic():
        ContentSaveSourceFactory(content_save=content_save, order=0)


@pytest.mark.django_db
def test_a_save_that_has_sources_cannot_be_deleted(mock_site_context):
    content_save = ContentSaveFactory()
    ContentSaveSourceFactory(content_save=content_save, order=0)

    with pytest.raises(ProtectedError):
        content_save.delete()
