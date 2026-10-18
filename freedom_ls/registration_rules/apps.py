from django.apps import AppConfig


class RegistrationRulesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "freedom_ls.registration_rules"
    label = "freedom_ls_registration_rules"
    verbose_name = "Registration rules"

    def ready(self) -> None:
        from freedom_ls.registration_rules import checks, signals  # noqa: F401
