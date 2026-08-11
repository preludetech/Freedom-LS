"""Tests for get_unique_slug."""

import pytest

from freedom_ls.accounts.factories import SiteFactory
from freedom_ls.content_engine.factories import TopicFactory
from freedom_ls.content_engine.models import Topic
from freedom_ls.site_aware_models.slugs import get_unique_slug


@pytest.mark.django_db
class TestGetUniqueSlug:
    def test_base_slug_returned_when_no_collision(self, mock_site_context) -> None:
        result = get_unique_slug(Topic, mock_site_context, "new-topic")

        assert result == "new-topic"

    def test_suffix_appended_on_collision(self, mock_site_context) -> None:
        TopicFactory(slug="existing-topic")

        result = get_unique_slug(Topic, mock_site_context, "existing-topic")

        assert result == "existing-topic-2"

    def test_suffix_increments_past_multiple_collisions(
        self, mock_site_context
    ) -> None:
        TopicFactory(slug="existing-topic")
        TopicFactory(slug="existing-topic-2")

        result = get_unique_slug(Topic, mock_site_context, "existing-topic")

        assert result == "existing-topic-3"

    def test_existing_uuid_excluded_from_collision_check(
        self, mock_site_context
    ) -> None:
        topic = TopicFactory(slug="my-topic")

        result = get_unique_slug(
            Topic, mock_site_context, "my-topic", existing_uuid=str(topic.id)
        )

        assert result == "my-topic"

    def test_invalid_existing_uuid_is_ignored(self, mock_site_context) -> None:
        TopicFactory(slug="my-topic")

        result = get_unique_slug(
            Topic, mock_site_context, "my-topic", existing_uuid="not-a-uuid"
        )

        assert result == "my-topic-2"

    def test_collision_detected_on_a_non_ambient_site(self, mock_site_context) -> None:
        """A caller may legitimately pass a site other than the ambient one.

        Without the _base_manager fix, SiteAwareManager ANDs the ambient site
        onto the query, so `site=<ambient> AND site=<other>` is never true and
        every candidate slug looks free — the collision on the foreign site
        would go undetected.
        """
        other_site = SiteFactory()
        TopicFactory(slug="shared-slug", site=other_site)

        result = get_unique_slug(Topic, other_site, "shared-slug")

        assert result == "shared-slug-2"
