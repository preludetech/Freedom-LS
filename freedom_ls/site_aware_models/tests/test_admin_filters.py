"""CompletionListFilter: the complete/not-complete filter the progress admins share.

Exercised through the topic progress changelist because a SimpleListFilter
needs a real ModelAdmin to read a queryset from; the filter itself is
site_aware_models', and form_engine's changelist mounts it too.
"""

from __future__ import annotations

import pytest

from django.urls import reverse
from django.utils import timezone

from freedom_ls.learner_progress.factories import TopicProgressFactory

pytestmark = pytest.mark.django_db

CHANGELIST_URL_NAME = "admin:freedom_ls_learner_progress_topicprogress_changelist"


@pytest.fixture
def one_of_each(mock_site_context):
    """A finished topic progress record and an unfinished one."""
    return (
        TopicProgressFactory(complete_time=timezone.now()),
        TopicProgressFactory(complete_time=None),
    )


def _visible_pks(response) -> list:
    return [row.pk for row in response.context["cl"].result_list]


def test_complete_keeps_only_the_finished_rows(staff_client, one_of_each) -> None:
    finished, _unfinished = one_of_each

    response = staff_client.get(
        reverse(CHANGELIST_URL_NAME), {"completion": "complete"}
    )

    assert _visible_pks(response) == [finished.pk]


def test_incomplete_keeps_only_the_unfinished_rows(staff_client, one_of_each) -> None:
    _finished, unfinished = one_of_each

    response = staff_client.get(
        reverse(CHANGELIST_URL_NAME), {"completion": "incomplete"}
    )

    assert _visible_pks(response) == [unfinished.pk]


def test_an_unrecognised_value_narrows_nothing(staff_client, one_of_each) -> None:
    """A hand-edited value leaves the list whole rather than emptying it."""
    response = staff_client.get(
        reverse(CHANGELIST_URL_NAME), {"completion": "nonsense"}
    )

    assert len(_visible_pks(response)) == 2
