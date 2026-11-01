from django.apps import AppConfig


class ApiAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "freedom_ls.api"
    label = "freedom_ls_api"
    verbose_name = "API"

    def ready(self) -> None:
        from . import checks, schema  # noqa: F401
