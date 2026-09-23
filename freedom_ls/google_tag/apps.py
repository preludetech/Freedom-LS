from django.apps import AppConfig


class GoogleTagAppConfig(AppConfig):
    name = "freedom_ls.google_tag"
    label = "freedom_ls_google_tag"
    verbose_name = "Google tag"

    def ready(self) -> None:
        from freedom_ls.google_tag import checks  # noqa: F401
