"""The Meta pixel's mapping from analytics events to `fbq(...)` calls."""

from __future__ import annotations

from freedom_ls.base.analytics_events import AnalyticsEvent, PixelCall

# Standard events go through fbq('track', ...); names Meta does not define go
# through fbq('trackCustom', ...). SignUp and CourseCompleted are final:
# operators build custom conversions on them.
MAPPING: dict[str, PixelCall] = {
    AnalyticsEvent.COURSE_REGISTERED: PixelCall("track", "CompleteRegistration"),
    AnalyticsEvent.COURSE_ACCESS_REQUESTED: PixelCall(
        "track", "SubmitApplication", {"request_kind": "application"}
    ),
    AnalyticsEvent.GENERATE_LEAD: PixelCall("track", "Lead"),
    AnalyticsEvent.SIGN_UP: PixelCall("trackCustom", "SignUp"),
    AnalyticsEvent.COURSE_COMPLETED: PixelCall("trackCustom", "CourseCompleted"),
}
