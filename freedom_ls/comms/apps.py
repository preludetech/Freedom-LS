from django.apps import AppConfig


class CommsConfig(AppConfig):
    name = "freedom_ls.comms"
    label = "freedom_ls_comms"
    verbose_name = "Notifications"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from freedom_ls.comms import checks  # noqa: F401
