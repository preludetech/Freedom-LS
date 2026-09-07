from django.apps import AppConfig


class MailAppConfig(AppConfig):
    name = "freedom_ls.mail"
    label = "freedom_ls_mail"
    verbose_name = "Mail"

    def ready(self) -> None:
        from freedom_ls.mail import checks  # noqa: F401
