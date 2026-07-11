from django.apps import AppConfig


class DeploymentAppConfig(AppConfig):
    name = "freedom_ls.deployment"

    def ready(self) -> None:
        from freedom_ls.deployment.sentry import init_sentry

        init_sentry()
