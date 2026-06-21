from django.apps import AppConfig


class CourseApplicationsConfig(AppConfig):
    label = "freedom_ls_course_applications"
    name = "freedom_ls.course_applications"

    def ready(self) -> None:
        # No signals in this spec — application-review-ui spec adds those.
        pass
