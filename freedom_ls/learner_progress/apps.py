from django.apps import AppConfig


class LearnerProgressConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "freedom_ls.learner_progress"
    label = "freedom_ls_learner_progress"

    def ready(self) -> None:
        from freedom_ls.learner_progress import signals  # noqa: F401
