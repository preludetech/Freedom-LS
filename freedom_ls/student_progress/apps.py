from django.apps import AppConfig


class StudentProgressConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "freedom_ls.student_progress"
    label = "freedom_ls_student_progress"

    def ready(self) -> None:
        # Import to run the register_event_type(...) calls at module top.
        from freedom_ls.student_progress import xapi_events  # noqa: F401
