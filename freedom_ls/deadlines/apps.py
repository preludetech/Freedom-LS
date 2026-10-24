from django.apps import AppConfig


class DeadlinesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "freedom_ls.deadlines"
    label = "freedom_ls_deadlines"
    verbose_name = "Deadlines"

    def ready(self) -> None:
        from freedom_ls.deadlines import signals  # noqa: F401
