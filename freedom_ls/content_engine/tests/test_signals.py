"""Tests for the signals content_engine sends while loading content."""

from __future__ import annotations

from pathlib import Path

import pytest

from freedom_ls.content_engine.management.commands.content_save import (
    save_content_to_db,
)
from freedom_ls.content_engine.models import ContentCollectionItem
from freedom_ls.content_engine.signals import collection_items_synced

COURSE_UUID = "71000000-0000-0000-0000-000000000001"


def _write_two_part_course(root: Path) -> None:
    (root / "course.md").write_text(
        f"---\ncontent_type: COURSE\ntitle: Signal Course\nuuid: {COURSE_UUID}\n---\n"
    )
    for number, part in enumerate(["01. One", "02. Two"], start=1):
        part_dir = root / part
        part_dir.mkdir()
        (part_dir / "part.yaml").write_text(
            f"---\ncontent_type: COURSE_PART\ntitle: {part}\n"
            f"uuid: 71000000-0000-0000-0000-00000000010{number}\n"
        )
        (part_dir / "topic.md").write_text(
            f"---\ncontent_type: TOPIC\ntitle: Topic {number}\n"
            f"uuid: 71000000-0000-0000-0000-00000000020{number}\n---\n\nBody.\n"
        )


class _Receiver:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def __call__(self, **kwargs: object) -> None:
        self.calls.append(kwargs)


@pytest.fixture
def receiver():
    connected = _Receiver()
    collection_items_synced.connect(connected, weak=False)
    yield connected
    collection_items_synced.disconnect(connected)


@pytest.mark.django_db
def test_signal_is_sent_once_per_load_with_created_and_written_rows(
    site, mock_site_context, tmp_path, receiver
):
    _write_two_part_course(tmp_path)

    save_content_to_db(tmp_path, site.name)

    assert len(receiver.calls) == 1
    call = receiver.calls[0]
    assert call["site"] == site
    assert call["sender"] is ContentCollectionItem
    # Two part rows in the course and one topic row in each part.
    created = call["created"]
    written = call["written"]
    assert isinstance(created, list)
    assert isinstance(written, list)
    assert len(created) == 4
    assert {row.pk for row in written} == {row.pk for row in created}
    assert {row.pk for row in created} == set(
        ContentCollectionItem.objects.values_list("pk", flat=True)
    )


@pytest.mark.django_db
def test_a_reload_writes_the_rows_but_creates_none(
    site, mock_site_context, tmp_path, receiver
):
    _write_two_part_course(tmp_path)
    save_content_to_db(tmp_path, site.name)

    save_content_to_db(tmp_path, site.name)

    assert len(receiver.calls) == 2
    second = receiver.calls[1]
    assert second["created"] == []
    assert len(second["written"]) == 4
