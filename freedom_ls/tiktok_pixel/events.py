"""The TikTok pixel's mapping from analytics events to `ttq.track(...)` calls."""

from __future__ import annotations

from freedom_ls.base.analytics_events import AnalyticsEvent, PixelCall

# TikTok has no separate custom-event call: every row goes through
# ttq.track(...), standard or custom name alike.
MAPPING: dict[str, PixelCall] = {
    AnalyticsEvent.COURSE_REGISTERED: PixelCall("track", "CompleteRegistration"),
    AnalyticsEvent.COURSE_ACCESS_REQUESTED: PixelCall(
        "track", "SubmitApplication", {"request_kind": "application"}
    ),
    AnalyticsEvent.GENERATE_LEAD: PixelCall("track", "SubmitForm"),
    AnalyticsEvent.SIGN_UP: PixelCall("track", "SignUp"),
    AnalyticsEvent.COURSE_COMPLETED: PixelCall("track", "CourseCompleted"),
}
