from django.apps import AppConfig


class CourseApplicationsConfig(AppConfig):
    label = "freedom_ls_course_applications"
    name = "freedom_ls.course_applications"
    verbose_name = "Course applications"

    def ready(self) -> None:
        # NOTE: application review will add its own signals here.
        from freedom_ls.course_applications import receivers  # noqa: F401
        from freedom_ls.course_applications.queries import (
            sitting_belongs_to_a_non_draft_application,
        )
        from freedom_ls.form_engine.sitting_locks import register_sitting_lock

        register_sitting_lock(sitting_belongs_to_a_non_draft_application)
