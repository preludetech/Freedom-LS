from django.apps import AppConfig


class CourseApplicationsConfig(AppConfig):
    label = "freedom_ls_course_applications"
    name = "freedom_ls.course_applications"

    def ready(self) -> None:
        # No signals yet; application review will add them.
        pass
