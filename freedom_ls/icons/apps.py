from django.apps import AppConfig


class IconsConfig(AppConfig):
    name = "freedom_ls.icons"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from freedom_ls.icons import checks  # noqa: F401
