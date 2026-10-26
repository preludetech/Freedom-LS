"""Tests for the migration that renames webhook event types to the audit
action codes, rewriting stored endpoint subscriptions."""

import importlib

import pytest

from django.apps import apps as django_apps
from django.contrib.sites.models import Site

from freedom_ls.webhooks.factories import WebhookEndpointFactory, WebhookEventFactory
from freedom_ls.webhooks.models import WebhookEndpoint, WebhookEvent
from freedom_ls.webhooks.registry import RENAMED_EVENT_TYPES

migration = importlib.import_module(
    "freedom_ls.webhooks.migrations.0002_rename_event_types"
)


@pytest.mark.django_db
class TestRenameEventTypes:
    def test_rewrites_a_subscription_through_the_map(
        self, mock_site_context: Site
    ) -> None:
        endpoint = WebhookEndpointFactory(
            event_types=["user.registered", "course.unregistered", "course.completed"]
        )

        migration.rename_forward(django_apps, None)

        endpoint.refresh_from_db()
        assert endpoint.event_types == [
            "user.signed_up",
            "registration.deactivated",
            "course.completed",
        ]

    def test_a_code_that_split_subscribes_to_both_new_codes(
        self, mock_site_context: Site
    ) -> None:
        endpoint = WebhookEndpointFactory(
            event_types=["course.registered", "cohort.course_registered"]
        )

        migration.rename_forward(django_apps, None)

        endpoint.refresh_from_db()
        assert endpoint.event_types == [
            "registration.added",
            "registration.reactivated",
            "cohort_registration.added",
            "cohort_registration.reactivated",
        ]

    def test_an_already_new_subscription_is_left_alone(
        self, mock_site_context: Site
    ) -> None:
        endpoint = WebhookEndpointFactory(
            event_types=["registration.added", "registration.reactivated"]
        )
        before = endpoint.updated_at

        migration.rename_forward(django_apps, None)

        endpoint.refresh_from_db()
        assert (endpoint.event_types, endpoint.updated_at) == (
            ["registration.added", "registration.reactivated"],
            before,
        )

    def test_the_registry_map_matches_the_migration(self) -> None:
        """dispatch_event matches an event queued under an old code through
        the registry's copy, which cannot drift from the frozen migration's."""
        assert RENAMED_EVENT_TYPES == migration.RENAMES

    def test_past_events_keep_the_code_that_was_sent(
        self, mock_site_context: Site
    ) -> None:
        WebhookEventFactory(event_type="course.registered")

        migration.rename_forward(django_apps, None)

        assert WebhookEvent._base_manager.get().event_type == "course.registered"

    def test_backward_collapses_the_split_codes(self, mock_site_context: Site) -> None:
        endpoint = WebhookEndpointFactory(
            event_types=[
                "user.signed_up",
                "registration.added",
                "registration.reactivated",
                "cohort_membership.removed",
            ]
        )

        migration.rename_backward(django_apps, None)

        assert WebhookEndpoint._base_manager.get(pk=endpoint.pk).event_types == [
            "user.registered",
            "course.registered",
            "cohort.member_removed",
        ]
