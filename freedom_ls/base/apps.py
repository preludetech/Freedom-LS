from django.apps import AppConfig


class BaseConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "freedom_ls.base"
    label = "freedom_ls_base"
    verbose_name = "Base"

    def ready(self) -> None:
        from . import checks  # noqa: F401
