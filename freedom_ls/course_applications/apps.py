from django.apps import AppConfig


class CourseApplicationsConfig(AppConfig):
    label = "freedom_ls_course_applications"
    name = "freedom_ls.course_applications"
    verbose_name = "Course applications"

    def ready(self) -> None:
        from django.contrib.auth.signals import user_logged_in

        from freedom_ls.course_applications.signals import claim_on_login

        user_logged_in.connect(
            claim_on_login, dispatch_uid="course_applications.claim_on_login"
        )
        # Application review will connect its own receivers here.
