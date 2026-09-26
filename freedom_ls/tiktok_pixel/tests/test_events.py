from __future__ import annotations

import pytest

from freedom_ls.base.analytics_events import (
    AnalyticsEventPayload,
    PixelCall,
    pixel_call,
)
from freedom_ls.tiktok_pixel.events import MAPPING


class TestMapping:
    @pytest.mark.parametrize(
        ("name", "params", "expected"),
        [
            ("course_registered", {}, PixelCall("track", "CompleteRegistration")),
            (
                "course_access_requested",
                {"request_kind": "application"},
                PixelCall(
                    "track", "SubmitApplication", {"request_kind": "application"}
                ),
            ),
            ("generate_lead", {}, PixelCall("track", "SubmitForm")),
            ("sign_up", {"method": "email"}, PixelCall("track", "SignUp")),
            ("course_completed", {}, PixelCall("track", "CourseCompleted")),
        ],
    )
    def test_a_mapped_row_gives_its_method_and_name(
        self, name: str, params: dict[str, str], expected: PixelCall
    ) -> None:
        event: AnalyticsEventPayload = {"name": name, "params": params}

        assert pixel_call(MAPPING, event) == expected

    def test_an_interest_registration_gives_none(self) -> None:
        event: AnalyticsEventPayload = {
            "name": "course_access_requested",
            "params": {"request_kind": "interest"},
        }

        assert pixel_call(MAPPING, event) is None

    def test_course_started_gives_none(self) -> None:
        event: AnalyticsEventPayload = {"name": "course_started", "params": {}}

        assert pixel_call(MAPPING, event) is None

    def test_an_unmapped_downstream_event_gives_none(self) -> None:
        event: AnalyticsEventPayload = {"name": "downstream_only", "params": {}}

        assert pixel_call(MAPPING, event) is None
