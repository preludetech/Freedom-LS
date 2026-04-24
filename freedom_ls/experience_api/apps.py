"""AppConfig for the generic xAPI event-logging infrastructure."""

from __future__ import annotations

from django.apps import AppConfig
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class ExperienceApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "freedom_ls.experience_api"
    label = "experience_api"

    def ready(self) -> None:
        self._check_task_backend()
        # Import the models module to register the pre_save signal
        # that mirrors Event.save's immutability guard.
        from freedom_ls.experience_api import models  # noqa: F401

    def _check_task_backend(self) -> None:
        """Refuse to boot with a non-`ImmediateBackend` unless explicitly acknowledged.

        A queued task backend needs a retry policy, dead-letter sink, and failure
        monitoring before it is safe to use for event writes (see spec §"Preconditions
        for switching off `ImmediateBackend`"). Until those land, only
        `ImmediateBackend` is supported; operators can override with a setting.
        """
        tasks_config = getattr(settings, "TASKS", {})
        default = tasks_config.get("default", {})
        backend = default.get("BACKEND", "")
        immediate = "django.tasks.backends.immediate.ImmediateBackend"
        ack = getattr(settings, "EXPERIENCE_API_QUEUED_BACKEND_OBSERVABILITY_OK", False)
        if backend and backend != immediate and not ack:
            raise ImproperlyConfigured(
                "experience_api refuses to boot with a non-ImmediateBackend "
                "TASKS default without EXPERIENCE_API_QUEUED_BACKEND_OBSERVABILITY_OK=True. "
                "See spec §'Preconditions for switching off ImmediateBackend'."
            )
