from django.apps import AppConfig


class PanelFrameworkConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "freedom_ls.panel_framework"
    label = "freedom_ls_panel_framework"
    verbose_name = "Panel framework"

    def ready(self) -> None:
        from django.core.checks import register

        from freedom_ls.panel_framework.checks import (
            check_icon_names,
            check_panels,
            check_reference_base_template,
            check_site_resolver,
            check_task_backend,
        )

        register(check_icon_names)
        register(check_panels)
        register(check_reference_base_template)
        register(check_task_backend)
        register(check_site_resolver)
