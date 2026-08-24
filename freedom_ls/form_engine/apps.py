from django.apps import AppConfig


class FormEngineConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "freedom_ls.form_engine"
    label = "freedom_ls_form_engine"

    def ready(self) -> None:
        from freedom_ls.form_engine import schema  # noqa: F401
