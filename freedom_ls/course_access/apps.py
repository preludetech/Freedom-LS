from django.apps import AppConfig


class CourseAccessConfig(AppConfig):
    label = "freedom_ls_course_access"
    name = "freedom_ls.course_access"

    def ready(self) -> None:
        from freedom_ls.course_access import checks  # noqa: F401
