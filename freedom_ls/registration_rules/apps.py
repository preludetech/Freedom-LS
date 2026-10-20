from django.apps import AppConfig, apps
from django.core.exceptions import ImproperlyConfigured


class RegistrationRulesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "freedom_ls.registration_rules"
    label = "freedom_ls_registration_rules"
    verbose_name = "Registration rules"

    def import_models(self) -> None:
        # Raised here rather than as a system check: the models, signals and
        # admin all import hr_attributes, so without it startup fails before
        # any check could run.
        if not apps.is_installed("freedom_ls.hr_attributes"):
            raise ImproperlyConfigured(
                "freedom_ls.registration_rules requires freedom_ls.hr_attributes. "
                'Add "freedom_ls.hr_attributes" to INSTALLED_APPS before '
                '"freedom_ls.registration_rules".'
            )
        super().import_models()

    def ready(self) -> None:
        from freedom_ls.registration_rules import checks, signals  # noqa: F401
