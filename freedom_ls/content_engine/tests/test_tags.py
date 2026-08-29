"""How `tags` is read off a content file, and what a reimport does to it."""

import pytest

from freedom_ls.content_engine.management.commands.content_save import save_topic
from freedom_ls.content_engine.models import Topic
from freedom_ls.content_engine.validate import parse_single_file

_TOPIC_UUID = "11111111-1111-4111-8111-111111111111"


def _topic_file(make_temp_file, tags_line: str):
    return make_temp_file(
        suffix=".md",
        content=(
            "---\n"
            "content_type: TOPIC\n"
            "title: Reimported Topic\n"
            f"uuid: {_TOPIC_UUID}\n"
            f"{tags_line}"
            "---\n"
        ),
    )


def _import(path, site):
    return save_topic(parse_single_file(path)[0], site, path.parent)


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


def test_frontmatter_with_a_bare_tags_key_parses_to_empty_list(make_temp_file):
    """YAML reads a valueless `tags:` as None; it means "no tags", not invalid."""
    content = """---
content_type: TOPIC
title: Topic With A Bare Tags Key
tags:
---
"""
    temp_file = make_temp_file(suffix=".md", content=content)
    parsed_items = parse_single_file(temp_file)

    assert len(parsed_items) == 1
    assert parsed_items[0].tags == []


@pytest.mark.django_db
def test_reimport_without_a_tags_key_keeps_the_stored_tags(
    site, mock_site_context, make_temp_file
):
    """A file that says nothing about tags must not clear them, as with meta."""
    path = _topic_file(make_temp_file, tags_line="")
    topic = _import(path, site)
    Topic.objects.filter(pk=topic.pk).update(tags=["curated-in-the-admin"])

    reimported = _import(path, site)

    assert reimported.tags == ["curated-in-the-admin"]


@pytest.mark.django_db
def test_reimport_with_an_empty_tags_key_clears_the_stored_tags(
    site, mock_site_context, make_temp_file
):
    """An explicit empty list is how a file says "this has no tags"."""
    path = _topic_file(make_temp_file, tags_line="tags: []\n")
    topic = _import(path, site)
    Topic.objects.filter(pk=topic.pk).update(tags=["curated-in-the-admin"])

    reimported = _import(path, site)

    assert reimported.tags == []


@pytest.mark.django_db
def test_reimport_replaces_the_stored_tags_with_the_files_own(
    site, mock_site_context, make_temp_file
):
    """A file listing tags is authoritative over whatever the admin curated."""
    path = _topic_file(make_temp_file, tags_line="tags: [python, advanced]\n")
    topic = _import(path, site)
    Topic.objects.filter(pk=topic.pk).update(tags=["curated-in-the-admin"])

    reimported = _import(path, site)

    assert reimported.tags == ["python", "advanced"]
