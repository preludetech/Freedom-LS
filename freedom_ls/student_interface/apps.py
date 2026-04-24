from django.apps import AppConfig


class StudentInterfaceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "freedom_ls.student_interface"
    label = "freedom_ls_student_interface"

    def ready(self) -> None:
        # Importing xapi_events runs the `register_event_type(...)` calls at
        # module top level, so the schemas land in the registry before any
        # view calls ``track()``. Same pattern used elsewhere for signal
        # registration.
        from freedom_ls.student_interface import xapi_events  # noqa: F401
