"""ContentTagListFilter: the tag sidebar shared by the content changelists.

Exercised through Topic's changelist because the filter needs a real
ModelAdmin to read a queryset from; the filter itself is content_base's and
serves form_engine's changelist too.
"""

from __future__ import annotations

import pytest

from django.urls import reverse

from freedom_ls.content_engine.factories import TopicFactory

TOPIC_CHANGELIST_URL_NAME = "admin:freedom_ls_content_engine_topic_changelist"


def _tag_filter_choices(response) -> set[str]:
    """The tag names the changelist sidebar offers, minus its "All" entry."""
    changelist = response.context["cl"]
    spec = next(spec for spec in changelist.filter_specs if str(spec.title) == "tags")
    return {
        choice["display"]
        for choice in spec.choices(changelist)
        if choice["query_string"] != "?"
    }


@pytest.mark.django_db
class TestTagFilter:
    def test_filtering_by_a_tag_narrows_the_changelist(self, staff_client) -> None:
        tagged = TopicFactory(title="Tagged", tags=["python", "advanced"])
        TopicFactory(title="Other", tags=["django"])

        response = staff_client.get(
            reverse(TOPIC_CHANGELIST_URL_NAME), {"tag": "python"}
        )

        assert [topic.pk for topic in response.context["cl"].result_list] == [tagged.pk]

    def test_the_filter_offers_every_stored_tag(self, staff_client) -> None:
        TopicFactory(tags=["python", "advanced"])
        TopicFactory(tags=["django"])

        response = staff_client.get(reverse(TOPIC_CHANGELIST_URL_NAME))

        assert _tag_filter_choices(response) == {"advanced", "django", "python"}

    def test_an_unknown_tag_matches_nothing(self, staff_client) -> None:
        TopicFactory(tags=["python"])

        response = staff_client.get(
            reverse(TOPIC_CHANGELIST_URL_NAME), {"tag": "nonexistent"}
        )

        assert list(response.context["cl"].result_list) == []
