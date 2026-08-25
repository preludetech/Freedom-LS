"""The progress admins render against the record-keyed models.

Every field name in a ModelAdmin is a string, so a stale one is a FieldError at
import or a 500 on the page -- never a type error. `CourseFormAttempt` reads
most of its columns through `form_progress`, which makes those paths
particularly easy to break from the form_engine side without noticing.
"""

from __future__ import annotations

import pytest

from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.learner_progress.factories import (
    CourseFormAttemptFactory,
    CourseProgressFactory,
    TopicProgressFactory,
)

pytestmark = pytest.mark.django_db

CHANGELIST_URL_NAMES = [
    "admin:freedom_ls_learner_progress_courseprogress_changelist",
    "admin:freedom_ls_learner_progress_topicprogress_changelist",
    "admin:freedom_ls_learner_progress_courseformattempt_changelist",
]


@pytest.fixture
def superuser_client(mock_site_context):
    client = Client()
    client.force_login(UserFactory(superuser=True))
    return client


@pytest.fixture
def progress_rows(mock_site_context):
    TopicProgressFactory()
    CourseProgressFactory()
    CourseFormAttemptFactory()


@pytest.mark.parametrize("url_name", CHANGELIST_URL_NAMES)
def test_changelist_renders_with_rows_present(
    superuser_client, progress_rows, url_name
):
    response = superuser_client.get(reverse(url_name))

    assert response.status_code == 200


@pytest.mark.parametrize("url_name", CHANGELIST_URL_NAMES)
def test_changelist_search_resolves_its_field_paths(
    superuser_client, progress_rows, url_name
):
    """A search_fields path that no longer exists raises rather than filtering."""
    response = superuser_client.get(reverse(url_name), {"q": "nobody@example.com"})

    assert response.status_code == 200


@pytest.mark.parametrize(
    ("url_name", "row_factory"),
    [
        (
            "admin:freedom_ls_learner_progress_courseprogress_change",
            CourseProgressFactory,
        ),
        (
            "admin:freedom_ls_learner_progress_topicprogress_change",
            TopicProgressFactory,
        ),
        (
            "admin:freedom_ls_learner_progress_courseformattempt_change",
            CourseFormAttemptFactory,
        ),
    ],
)
def test_change_form_renders(superuser_client, url_name, row_factory):
    row = row_factory()

    response = superuser_client.get(reverse(url_name, args=[row.pk]))

    assert response.status_code == 200
