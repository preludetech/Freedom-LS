"""Tests for the progress and at-risk flag badges."""

from __future__ import annotations

import pytest

from django.template.loader import render_to_string

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


def _badges_html(flag: AtRiskFlag) -> str:
    return render_to_string(
        "educator_interface/partials/learner_badges.html",
        {"completion_percentage": 0, "flags": [flag]},
    )


@pytest.mark.django_db
class TestLearnerBadgesReason:
    def test_a_reason_that_only_restates_the_label_is_left_out(self) -> None:
        flag = AtRiskFlag(
            rule_id="no_activity",
            label="No recorded activity",
            reason="Has not started any course item.",
            severity="error",
            reason_adds_information=False,
        )

        html = _badges_html(flag)

        assert "No recorded activity" in html
        assert "Has not started any course item." not in html

    def test_a_reason_that_adds_information_prints_beside_the_label(self) -> None:
        flag = AtRiskFlag(
            rule_id="inactive",
            label="No activity recently",
            reason="No activity recorded in over 7 days.",
            severity="warning",
            reason_adds_information=True,
        )

        html = _badges_html(flag)

        assert "No activity recently" in html
        assert "No activity recorded in over 7 days." in html
