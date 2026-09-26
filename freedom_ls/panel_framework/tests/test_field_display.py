"""Tests for the vendored field-label and field-display helpers."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from django.contrib.admin.utils import display_for_field as django_display_for_field
from django.contrib.admin.utils import display_for_value as django_display_for_value
from django.contrib.admin.utils import label_for_field as django_label_for_field
from django.contrib.admin.utils import lookup_field as django_lookup_field
from django.db.models import Value
from django.db.models.functions import Concat

from freedom_ls.panel_framework.field_display import (
    display_for_field,
    display_for_value,
    label_for_field,
    lookup_field,
)

from .conftest import StubChild, StubModel, _make_stub, _make_stub_child

# ---------------------------------------------------------------------------
# label_for_field
# ---------------------------------------------------------------------------


def test_label_for_field_returns_the_verbose_name_for_a_plain_field() -> None:
    assert label_for_field("name", StubModel) == "name"


def test_label_for_field_survives_an_acronym_verbose_name() -> None:
    # "SAT score" must not come back mangled ("Sat Score") the way .title() would.
    assert label_for_field("sat_score", StubModel) == "SAT score"


def test_label_for_field_resolves_a_property() -> None:
    assert label_for_field("display_name", StubModel) == "Display name"


def test_label_for_field_resolves_a_method() -> None:
    assert label_for_field("describe", StubModel) == "Describe"


def test_label_for_field_resolves_a_dunder_path_to_the_leaf_fields_verbose_name() -> (
    None
):
    # The leaf field's own verbose_name, not pretty_name of the whole path.
    assert label_for_field("parent__sat_score", StubChild) == "SAT score"


def test_label_for_field_raises_attribute_error_naming_the_model_for_an_unknown_name() -> (
    None
):
    with pytest.raises(AttributeError, match=r"freedom_ls_panel_framework\.StubModel"):
        label_for_field("no_such_field", StubModel)


def test_label_for_field_matches_django_for_a_plain_field() -> None:
    assert label_for_field("name", StubModel) == django_label_for_field(
        "name", StubModel
    )


def test_label_for_field_matches_django_for_a_property() -> None:
    assert label_for_field("display_name", StubModel) == django_label_for_field(
        "display_name", StubModel
    )


# ---------------------------------------------------------------------------
# lookup_field / display_for_field / display_for_value
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_choices_field_displays_its_label() -> None:
    # Arrange
    instance = _make_stub(kind="b")

    # Act
    field, value = lookup_field("kind", instance)
    assert field is not None
    display = display_for_field(value, field, "-")

    # Assert
    assert display == "Beta"


@pytest.mark.django_db
def test_none_value_displays_the_empty_value_placeholder() -> None:
    # Arrange
    instance = _make_stub(sat_score=None)

    # Act
    field, value = lookup_field("sat_score", instance)
    assert field is not None
    display = display_for_field(value, field, "-")

    # Assert
    assert display == "-"


@pytest.mark.django_db
def test_boolean_field_value_comes_back_as_a_bool() -> None:
    # Arrange
    instance = _make_stub(is_active=False)

    # Act
    field, value = lookup_field("is_active", instance)
    assert field is not None
    display = display_for_field(value, field, "-")

    # Assert
    assert display is False


@pytest.mark.django_db
def test_property_value_resolves_through_lookup_field() -> None:
    # Arrange
    instance = _make_stub(name="freddy")

    # Act
    field, value = lookup_field("display_name", instance)
    display = display_for_value(value, "-")

    # Assert
    assert field is None
    assert display == "FREDDY"


@pytest.mark.django_db
def test_method_value_resolves_through_lookup_field() -> None:
    # Arrange
    instance = _make_stub(name="freddy", kind="a")

    # Act
    field, value = lookup_field("describe", instance)
    display = display_for_value(value, "-")

    # Assert
    assert field is None
    assert display == "freddy (a)"


@pytest.mark.django_db
def test_annotation_value_resolves_through_lookup_field() -> None:
    # Arrange
    _make_stub(name="freddy")
    instance = StubModel.objects.annotate(shout=Concat("name", Value("!"))).get(
        name="freddy"
    )

    # Act
    field, value = lookup_field("shout", instance)
    display = display_for_value(value, "-")

    # Assert
    assert field is None
    assert display == "freddy!"


@pytest.mark.django_db
def test_dunder_path_value_resolves_through_a_relation() -> None:
    # Arrange
    parent = _make_stub(kind="b")
    child = _make_stub_child(parent=parent)

    # Act
    field, value = lookup_field("parent__kind", child)
    assert field is not None
    display = display_for_field(value, field, "-")

    # Assert
    assert display == "Beta"


@pytest.mark.django_db
def test_missing_dunder_path_segment_returns_none_field_and_value() -> None:
    # Arrange
    parent = _make_stub()
    child = _make_stub_child(parent=parent)

    # Act
    field, value = lookup_field("parent__no_such_attr", child)

    # Assert
    assert field is None
    assert value is None


# ---------------------------------------------------------------------------
# Parity with django.contrib.admin.utils, over the divergences this module
# deliberately keeps: a bool instead of icon HTML, no URL/file links, no
# password branch.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "make_input",
    [
        pytest.param(lambda: ("name", _make_stub(name="parity")), id="plain_field"),
        pytest.param(lambda: ("kind", _make_stub(kind="a")), id="choices_field"),
        pytest.param(
            lambda: ("sat_score", _make_stub(sat_score=None)), id="empty_field"
        ),
        pytest.param(lambda: ("sat_score", _make_stub(sat_score=1400)), id="int_field"),
    ],
)
def test_display_for_field_matches_django_for_non_diverging_inputs(
    make_input: Callable[[], tuple[str, StubModel]],
) -> None:
    # Arrange
    name, instance = make_input()
    ours_field, ours_value = lookup_field(name, instance)
    theirs_field, _theirs_attr, theirs_value = django_lookup_field(name, instance)
    assert ours_field is not None
    assert theirs_field is not None

    # Act
    ours = display_for_field(ours_value, ours_field, "-")
    theirs = django_display_for_field(theirs_value, theirs_field, "-")

    # Assert
    assert ours == theirs


@pytest.mark.django_db
def test_display_for_field_diverges_from_django_for_a_boolean_by_returning_a_bool() -> (
    None
):
    # Arrange
    instance = _make_stub(is_active=True)
    ours_field, ours_value = lookup_field("is_active", instance)
    assert ours_field is not None

    # Act
    ours = display_for_field(ours_value, ours_field, "-")
    theirs = django_display_for_field(ours_value, ours_field, "-")

    # Assert: Django renders an <img> icon; the vendored copy returns the bool.
    assert ours is True
    assert theirs != ours


def test_display_for_value_matches_django_for_a_plain_string() -> None:
    assert display_for_value("hello", "-") == django_display_for_value("hello", "-")
