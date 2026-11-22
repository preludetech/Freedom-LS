from django.apps import AppConfig


class RevisionAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "freedom_ls.revision"
    label = "freedom_ls_revision"
    verbose_name = "Revision"

    def ready(self) -> None:
        from freedom_ls.revision import signals  # noqa: F401
