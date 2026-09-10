from django.apps import AppConfig


class ReferralTrackingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "freedom_ls.referral_tracking"
    label = "freedom_ls_referral_tracking"
    verbose_name = "Referral tracking"

    def ready(self) -> None:
        from freedom_ls.referral_tracking import signals  # noqa: F401
