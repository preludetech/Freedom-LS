from django.apps import AppConfig


class IconsConfig(AppConfig):
    name = "freedom_ls.icons"
    verbose_name = "Icons"

    def ready(self) -> None:
        from freedom_ls.icons import checks  # noqa: F401
