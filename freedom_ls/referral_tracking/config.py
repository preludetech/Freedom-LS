from __future__ import annotations

from freedom_ls.base.app_settings import AppSettings, Setting


class ReferralTrackingSettings(AppSettings):
    REFERRAL_TRACKING_COOKIE_NAME: str
    REFERRAL_TRACKING_COOKIE_MAX_AGE_DAYS: int
    REFERRAL_TRACKING_FIRST_TOUCH_KEY_CAP: int
    REFERRAL_TRACKING_INACTIVE_DESTINATION: str

    declared_settings = {
        "REFERRAL_TRACKING_COOKIE_NAME": Setting(default="fls_attribution"),
        "REFERRAL_TRACKING_COOKIE_MAX_AGE_DAYS": Setting(default=90),
        "REFERRAL_TRACKING_FIRST_TOUCH_KEY_CAP": Setting(default=1000),
        "REFERRAL_TRACKING_INACTIVE_DESTINATION": Setting(default="/"),
    }


config = ReferralTrackingSettings()
