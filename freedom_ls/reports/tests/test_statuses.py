"""Tests for the progress status a recomputed completion falls in."""

from __future__ import annotations

import pytest

from freedom_ls.reports.statuses import ProgressStatus, progress_status


@pytest.mark.parametrize(
    ("completion", "expected"),
    [
        (0, ProgressStatus.NOT_STARTED),
        (1, ProgressStatus.IN_PROGRESS),
        (99, ProgressStatus.IN_PROGRESS),
        (100, ProgressStatus.COMPLETE),
    ],
)
def test_a_completion_percentage_maps_to_its_status(
    completion: int, expected: ProgressStatus
) -> None:
    assert progress_status(completion) is expected


def test_the_status_labels_are_the_words_educators_read() -> None:
    assert [status.label for status in ProgressStatus] == [
        "Not started",
        "In progress",
        "Complete",
    ]
