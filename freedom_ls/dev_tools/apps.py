from django.apps import AppConfig


class DevToolsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "freedom_ls.dev_tools"
    label = "freedom_ls_dev_tools"
    verbose_name = "Dev tools"
