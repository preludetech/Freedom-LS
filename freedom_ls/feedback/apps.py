from django.apps import AppConfig


class FeedbackConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "freedom_ls.feedback"
    label = "freedom_ls_feedback"

    def ready(self) -> None:
        import freedom_ls.feedback.receivers  # noqa: F401
        from freedom_ls.feedback.registry import register_trigger_point

        register_trigger_point(
            "course_completed", "Fired when a user completes a course"
        )
        register_trigger_point("topic_completed", "Fired when a user completes a topic")
