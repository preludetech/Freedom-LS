from django.apps import AppConfig


class OrganisationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "freedom_ls.organisations"
    label = "freedom_ls_organisations"

    def ready(self) -> None:
        from . import signals  # noqa: F401
