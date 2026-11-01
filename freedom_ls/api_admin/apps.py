from django.apps import AppConfig, apps
from django.core.exceptions import ImproperlyConfigured


class ApiAdminAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "freedom_ls.api_admin"
    label = "freedom_ls_api_admin"
    verbose_name = "API keys"

    def import_models(self) -> None:
        # Raised here rather than as a system check: admin.py imports ApiKey
        # during admin autodiscovery, before any check could run.
        if not apps.is_installed("freedom_ls.api"):
            raise ImproperlyConfigured(
                "freedom_ls.api_admin requires freedom_ls.api. "
                'Add "freedom_ls.api" to INSTALLED_APPS before "freedom_ls.api_admin".'
            )
        super().import_models()
