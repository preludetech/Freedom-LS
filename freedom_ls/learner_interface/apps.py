from django.apps import AppConfig


class LearnerInterfaceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "freedom_ls.learner_interface"
    label = "freedom_ls_learner_interface"
    verbose_name = "Learner interface"

    def ready(self) -> None:
        from freedom_ls.learner_interface import checks  # noqa: F401
