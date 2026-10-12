from django.apps import AppConfig


class CourseApplicationsConfig(AppConfig):
    label = "freedom_ls_course_applications"
    name = "freedom_ls.course_applications"
    verbose_name = "Course applications"

    def ready(self) -> None:
        # NOTE: application review will add its own signals here.
        from freedom_ls.course_applications import receivers  # noqa: F401
