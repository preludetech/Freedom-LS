from django.apps import AppConfig


class EducatorInterfaceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "freedom_ls.educator_interface"
    label = "freedom_ls_educator_interface"
    verbose_name = "Educator interface"

    def ready(self) -> None:
        from freedom_ls.audit_log.actions import register_describe
        from freedom_ls.educator_interface.members import describe_role_change

        register_describe("role.granted", describe_role_change)
        register_describe("role.removed", describe_role_change)
