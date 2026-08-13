from django.apps import AppConfig


class ReportsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "freedom_ls.reports"
    label = "freedom_ls_reports"

    def ready(self) -> None:
        from freedom_ls.reports import checks  # noqa: F401
