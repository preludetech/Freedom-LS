"""Tests for BaseContent.tags: an ArrayField of strings, not a bare JSON blob."""

import pytest

from freedom_ls.content_engine.factories import TopicFactory
from freedom_ls.content_engine.models import Topic
from freedom_ls.content_engine.validate import parse_single_file


@pytest.mark.django_db
def test_tags_round_trips_list_of_strings_on_topic(mock_site_context):
    topic = TopicFactory(tags=["python", "advanced"])
    topic.refresh_from_db()
    assert topic.tags == ["python", "advanced"]


@pytest.mark.django_db
def test_tags_contains_lookup_matches_single_tag(mock_site_context):
    TopicFactory(tags=["python", "advanced"])
    assert Topic.objects.filter(tags__contains=["python"]).exists()


@pytest.mark.django_db
def test_topic_tags_defaults_to_empty_list(mock_site_context):
    topic = TopicFactory()
    topic.refresh_from_db()
    assert topic.tags == []


@pytest.mark.django_db
def test_frontmatter_without_tags_key_parses_to_empty_list(make_temp_file):
    content = """---
content_type: TOPIC
title: Topic Without Tags
---
"""
    temp_file = make_temp_file(suffix=".md", content=content)
    parsed_items = parse_single_file(temp_file)

    assert len(parsed_items) == 1
    assert parsed_items[0].tags == []
