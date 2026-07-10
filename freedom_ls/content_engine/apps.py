from django.apps import AppConfig


class ContentEngineConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "freedom_ls.content_engine"
    label = "freedom_ls_content_engine"

    def ready(self) -> None:
        from freedom_ls.content_engine import checks  # noqa: F401
