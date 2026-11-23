"""Tests for the course part localStorage keys."""

from __future__ import annotations

from freedom_ls.learner_interface.templatetags.course_storage_keys import (
    course_part_storage_key,
)


def test_a_learning_path_part_key_has_no_scope() -> None:
    assert course_part_storage_key("flying", 2) == "coursePart_flying_2"


def test_a_scoped_part_key_differs_from_the_learning_path_key() -> None:
    assert course_part_storage_key("flying", 2, "reference") == (
        "coursePart_reference_flying_2"
    )
