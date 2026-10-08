from django.apps import AppConfig


class MessagingPolicyConfig(AppConfig):
    name = "freedom_ls.messaging_policy"
    label = "freedom_ls_messaging_policy"
    verbose_name = "Messaging policy"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from freedom_ls.messaging_policy import checks  # noqa: F401
