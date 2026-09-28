from django.apps import AppConfig


class LearnerManagementConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "freedom_ls.learner_management"
    label = "freedom_ls_learner_management"
    verbose_name = "Learner management"

    def ready(self) -> None:
        from freedom_ls.learner_management import signals  # noqa: F401
