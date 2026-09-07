"""CompletionListFilter: the complete/not-complete filter the progress admins share.

Exercised through the topic progress changelist because a SimpleListFilter
needs a real ModelAdmin to read a queryset from; the filter itself is
site_aware_models', and form_engine's changelist mounts it too.
"""

from __future__ import annotations

from datetime import UTC, datetime

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


class TestInclusiveRangeDateTimeFilter:
    """The date range the progress admins share, driven the way a person drives it.

    Unfold's own ``RangeDateTimeFilter`` reads a date and a time per bound and
    applies the bound only when *both* are filled, so a person who fills the two
    date boxes and presses Apply gets the unfiltered list back with nothing to
    say why. These tests pin the forgiving behaviour: a blank time means the
    start of that day on the lower bound and the end of it on the upper, and an
    explicit time still wins.
    """

    @pytest.fixture
    def three_days(self, mock_site_context):
        """Records finished on the 4th (early), the 5th (late), and the 7th."""
        early_on_the_4th = TopicProgressFactory(
            complete_time=datetime(2026, 9, 4, 0, 30, tzinfo=UTC)
        )
        late_on_the_5th = TopicProgressFactory(
            complete_time=datetime(2026, 9, 5, 23, 30, tzinfo=UTC)
        )
        on_the_7th = TopicProgressFactory(
            complete_time=datetime(2026, 9, 7, 12, 0, tzinfo=UTC)
        )
        return early_on_the_4th, late_on_the_5th, on_the_7th

    def test_dates_alone_narrow_to_that_window(self, staff_client, three_days) -> None:
        """The bug: two dates and Apply used to return every row."""
        early_on_the_4th, late_on_the_5th, _on_the_7th = three_days

        response = staff_client.get(
            reverse(CHANGELIST_URL_NAME),
            {"complete_time_from_0": "2026-09-04", "complete_time_to_0": "2026-09-05"},
        )

        assert sorted(_visible_pks(response)) == sorted(
            [early_on_the_4th.pk, late_on_the_5th.pk]
        )

    def test_the_end_date_includes_the_whole_of_that_day(
        self, staff_client, three_days
    ) -> None:
        """A record at 23:30 on the end date is inside the range, not outside it."""
        _early_on_the_4th, late_on_the_5th, _on_the_7th = three_days

        response = staff_client.get(
            reverse(CHANGELIST_URL_NAME),
            {"complete_time_from_0": "2026-09-05", "complete_time_to_0": "2026-09-05"},
        )

        assert _visible_pks(response) == [late_on_the_5th.pk]

    def test_a_lower_bound_alone_narrows(self, staff_client, three_days) -> None:
        _early_on_the_4th, late_on_the_5th, on_the_7th = three_days

        response = staff_client.get(
            reverse(CHANGELIST_URL_NAME), {"complete_time_from_0": "2026-09-05"}
        )

        assert sorted(_visible_pks(response)) == sorted(
            [late_on_the_5th.pk, on_the_7th.pk]
        )

    def test_an_explicit_time_still_wins(self, staff_client, three_days) -> None:
        """Filling the time box narrows within the day rather than being ignored."""
        _early_on_the_4th, late_on_the_5th, _on_the_7th = three_days

        response = staff_client.get(
            reverse(CHANGELIST_URL_NAME),
            {
                "complete_time_from_0": "2026-09-05",
                "complete_time_from_1": "12:00:00",
                "complete_time_to_0": "2026-09-05",
            },
        )

        assert _visible_pks(response) == [late_on_the_5th.pk]

    def test_an_explicit_upper_time_excludes_later_that_day(
        self, staff_client, three_days
    ) -> None:
        """The end-of-day default must not override a time the person typed."""
        _early_on_the_4th, _late_on_the_5th, _on_the_7th = three_days

        response = staff_client.get(
            reverse(CHANGELIST_URL_NAME),
            {
                "complete_time_from_0": "2026-09-05",
                "complete_time_to_0": "2026-09-05",
                "complete_time_to_1": "12:00:00",
            },
        )

        assert _visible_pks(response) == []

    def test_both_bounds_blank_narrows_nothing(self, staff_client, three_days) -> None:
        response = staff_client.get(
            reverse(CHANGELIST_URL_NAME),
            {"complete_time_from_0": "", "complete_time_to_0": ""},
        )

        assert len(_visible_pks(response)) == 3
