from __future__ import annotations

import pytest

from freedom_ls.base.analytics_events import (
    AnalyticsEventPayload,
    PixelCall,
    pixel_call,
)
from freedom_ls.meta_pixel.events import MAPPING


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
            ("generate_lead", {}, PixelCall("track", "Lead")),
            (
                "sign_up",
                {"method": "email"},
                PixelCall("trackCustom", "SignUp"),
            ),
            (
                "course_completed",
                {},
                PixelCall("trackCustom", "CourseCompleted"),
            ),
            ("course_access_requested", {"request_kind": "interest"}, None),
            ("course_started", {}, None),
            ("downstream_only", {}, None),
        ],
    )
    def test_event_maps_to_its_platform_call_or_none(
        self, name: str, params: dict[str, str], expected: PixelCall | None
    ) -> None:
        event: AnalyticsEventPayload = {"name": name, "params": params}

        assert pixel_call(MAPPING, event) == expected
