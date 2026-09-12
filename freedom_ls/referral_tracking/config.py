from __future__ import annotations

from freedom_ls.base.app_settings import AppSettings, Setting


class ReferralTrackingSettings(AppSettings):
    REFERRAL_TRACKING_COOKIE_NAME: str
    REFERRAL_TRACKING_COOKIE_MAX_AGE_DAYS: int
    REFERRAL_TRACKING_FIRST_TOUCH_KEY_CAP: int
    REFERRAL_TRACKING_INACTIVE_DESTINATION: str
    REFERRAL_TRACKING_HIT_LOG_LIMIT: int
    REFERRAL_TRACKING_HIT_LOG_WINDOW_SECONDS: int

    declared_settings = {
        "REFERRAL_TRACKING_COOKIE_NAME": Setting(default="fls_attribution"),
        "REFERRAL_TRACKING_COOKIE_MAX_AGE_DAYS": Setting(default=90),
        "REFERRAL_TRACKING_FIRST_TOUCH_KEY_CAP": Setting(default=1000),
        "REFERRAL_TRACKING_INACTIVE_DESTINATION": Setting(default="/"),
        # How many hits on one code one client may write to the hit log per
        # window. Set the limit to 0 to log every hit instead.
        "REFERRAL_TRACKING_HIT_LOG_LIMIT": Setting(default=30),
        "REFERRAL_TRACKING_HIT_LOG_WINDOW_SECONDS": Setting(default=3600),
    }


config = ReferralTrackingSettings()
