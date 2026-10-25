from django.apps import AppConfig, apps
from django.core.exceptions import ImproperlyConfigured

_REQUIRED_APPS = ("freedom_ls.hr_attributes", "freedom_ls.course_recommendations")


class RegistrationRulesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "freedom_ls.registration_rules"
    label = "freedom_ls_registration_rules"
    verbose_name = "Registration rules"

    def import_models(self) -> None:
        # Raised here rather than as a system check: the models, signals and
        # admin all import these apps, so without one startup fails before any
        # check could run.
        for app in _REQUIRED_APPS:
            if not apps.is_installed(app):
                raise ImproperlyConfigured(
                    f"freedom_ls.registration_rules requires {app}. "
                    f'Add "{app}" to INSTALLED_APPS before "freedom_ls.registration_rules".'
                )
        super().import_models()

    def ready(self) -> None:
        from freedom_ls.registration_rules import checks, signals  # noqa: F401
