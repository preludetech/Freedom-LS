from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "freedom_ls.accounts"
    label = "freedom_ls_accounts"

    def ready(self) -> None:
        # Register system checks on app load.
        from . import checks  # noqa: F401
