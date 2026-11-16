from __future__ import annotations

from freedom_ls.base.app_settings import AppSettings, Setting


class ReferralTrackingSettings(AppSettings):
    REFERRAL_TRACKING_COOKIE_NAME: str
    REFERRAL_TRACKING_COOKIE_MAX_AGE_DAYS: int
    REFERRAL_TRACKING_FIRST_TOUCH_KEY_CAP: int
    REFERRAL_TRACKING_INACTIVE_DESTINATION: str
    REFERRAL_TRACKING_HIT_LOG_LIMIT: int
    REFERRAL_TRACKING_HIT_LOG_WINDOW_SECONDS: int
    REFERRAL_TRACKING_ATTRIBUTION_WINDOW_DAYS: int
    REFERRAL_TRACKING_MAX_COOKIE_TOUCHES: int
    REFERRAL_TRACKING_TOUCH_RETENTION_DAYS: int
    REFERRAL_TRACKING_HIT_RETENTION_DAYS: int

    declared_settings = {
        "REFERRAL_TRACKING_COOKIE_NAME": Setting(default="fls_attribution"),
        "REFERRAL_TRACKING_COOKIE_MAX_AGE_DAYS": Setting(default=90),
        "REFERRAL_TRACKING_FIRST_TOUCH_KEY_CAP": Setting(default=1000),
        "REFERRAL_TRACKING_INACTIVE_DESTINATION": Setting(default="/"),
        # How many hits on one code one client may write to the hit log per
        # window. Set the limit to 0 to log every hit instead.
        "REFERRAL_TRACKING_HIT_LOG_LIMIT": Setting(default=30),
        "REFERRAL_TRACKING_HIT_LOG_WINDOW_SECONDS": Setting(default=3600),
        # How far back a conversion looks for the touches in play.
        "REFERRAL_TRACKING_ATTRIBUTION_WINDOW_DAYS": Setting(default=90),
        # How many later landings the cookie remembers beside the first touch.
        # The oldest is dropped past this, and a bigger number only helps while
        # the cookie still fits the browser limit.
        "REFERRAL_TRACKING_MAX_COOKIE_TOUCHES": Setting(default=10),
        # Days an attribution touch is kept before housekeeping deletes it. A
        # touch a conversion names is kept regardless. Must be at least
        # REFERRAL_TRACKING_ATTRIBUTION_WINDOW_DAYS, which check E003 enforces.
        "REFERRAL_TRACKING_TOUCH_RETENTION_DAYS": Setting(default=365),
        # Days a referral code hit is kept before housekeeping deletes it. A
        # code's hit_count is a separate counter and is not reduced.
        "REFERRAL_TRACKING_HIT_RETENTION_DAYS": Setting(default=365),
    }


config = ReferralTrackingSettings()
