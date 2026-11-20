"""Tests for the educator interface's template tags."""

from __future__ import annotations

from uuid import uuid4

from freedom_ls.educator_interface.avatars import PersonAvatar
from freedom_ls.educator_interface.templatetags.educator_tags import (
    RowAvatar,
    learner_avatar_tag,
)


def test_a_resolved_learner_gives_their_user_pk_and_picture() -> None:
    learner_id = uuid4()
    avatars = {learner_id: PersonAvatar(1234, "/media/pic.png")}

    assert learner_avatar_tag(avatars, learner_id) == RowAvatar(
        "1234", "/media/pic.png"
    )


def test_a_resolved_learner_without_a_picture_gives_an_empty_picture_url() -> None:
    learner_id = uuid4()

    assert learner_avatar_tag(
        {learner_id: PersonAvatar(7, None)}, learner_id
    ) == RowAvatar("7", "")


def test_an_unresolved_learner_falls_back_to_the_learner_id() -> None:
    learner_id = uuid4()

    assert learner_avatar_tag({}, learner_id) == RowAvatar(str(learner_id), "")


def test_avatars_missing_from_the_context_falls_back_to_the_learner_id() -> None:
    learner_id = uuid4()

    assert learner_avatar_tag("", learner_id) == RowAvatar(str(learner_id), "")
