"""Tests for the progress and at-risk flag badges."""

from __future__ import annotations

import pytest

from freedom_ls.educator_interface.panels.common.report import (
    PROGRESS_STATUS_TONES,
    flag_badge,
    progress_status_badge,
)
from freedom_ls.reports.report_data import AtRiskFlag
from freedom_ls.reports.statuses import ProgressStatus


@pytest.mark.django_db
class TestProgressBadges:
    def test_the_three_statuses_map_to_muted_info_and_success(self) -> None:
        assert [PROGRESS_STATUS_TONES[status] for status in ProgressStatus] == [
            "muted",
            "info",
            "success",
        ]

    def test_a_completion_percentage_becomes_its_status_badge(self) -> None:
        badge = progress_status_badge(50)

        assert (badge.tone, badge.label) == ("info", "In progress")

    def test_a_flag_badge_is_toned_by_the_flags_severity(self) -> None:
        flag = AtRiskFlag(
            rule_id="inactive",
            label="No activity recently",
            reason="No activity recorded in over 7 days.",
            severity="warning",
        )

        badge = flag_badge(flag)

        assert (badge.tone, badge.label) == ("warning", "No activity recently")
