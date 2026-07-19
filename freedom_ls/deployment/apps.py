from django.apps import AppConfig


class DeploymentAppConfig(AppConfig):
    name = "freedom_ls.deployment"
    label = "freedom_ls_deployment"

    def ready(self) -> None:
        from freedom_ls.deployment import checks  # noqa: F401
        from freedom_ls.deployment.sentry import init_sentry

        init_sentry()
