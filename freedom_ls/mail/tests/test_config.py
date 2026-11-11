"""Tests for the mail app's declared settings."""

from __future__ import annotations

from django_tasks_db.management.commands.prune_db_task_results import Command

from freedom_ls.mail.config import config


class TestEmailUpstreamBackendDefault:
    def test_defaults_to_djangos_smtp_backend(self) -> None:
        assert (
            config.EMAIL_UPSTREAM_BACKEND
            == "django.core.mail.backends.smtp.EmailBackend"
        )

    def test_the_default_is_never_the_queueing_backend(self) -> None:
        # A default that pointed at the queue would make every deployment that
        # queues mail and did not override it enqueue forever without sending any.
        assert (
            config.EMAIL_UPSTREAM_BACKEND
            != "freedom_ls.mail.backends.QueuedEmailBackend"
        )


class TestRetryLadderBounds:
    def test_the_full_ladder_ends_before_task_results_are_pruned(self) -> None:
        prune_days = (
            Command().create_parser("manage.py", "x").get_default("min_age_days")
        )
        full_jitter = 1 + config.EMAIL_RETRY_JITTER_RATIO

        ladder_seconds = sum(config.EMAIL_RETRY_DELAYS) * full_jitter

        assert ladder_seconds < prune_days * 24 * 3600

    def test_the_ladder_has_a_delay_for_every_retry(self) -> None:
        assert len(config.EMAIL_RETRY_DELAYS) + 1 >= config.EMAIL_MAX_ATTEMPTS
