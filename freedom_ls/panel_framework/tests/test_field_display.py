"""Tests for the vendored field-label and field-display helpers, and the link data-table cell that renders through them."""

from __future__ import annotations

from collections.abc import Callable

import lxml.html
import pytest

from django.contrib.admin.utils import display_for_field as django_display_for_field
from django.contrib.admin.utils import display_for_value as django_display_for_value
from django.contrib.admin.utils import label_for_field as django_label_for_field
from django.contrib.admin.utils import lookup_field as django_lookup_field
from django.db.models import Value
from django.db.models.functions import Concat
from django.template.loader import render_to_string

from freedom_ls.panel_framework.field_display import (
    display_for_field,
    display_for_value,
    label_for_field,
    lookup_field,
)

from .helpers import make_stub, make_stub_child
from .stub_models import StubChild, StubModel

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
    instance = make_stub(kind="b")

    # Act
    field, value = lookup_field("kind", instance)
    assert field is not None
    display = display_for_field(value, field, "-")

    # Assert
    assert display == "Beta"


@pytest.mark.django_db
def test_none_value_displays_the_empty_value_placeholder() -> None:
    # Arrange
    instance = make_stub(sat_score=None)

    # Act
    field, value = lookup_field("sat_score", instance)
    assert field is not None
    display = display_for_field(value, field, "-")

    # Assert
    assert display == "-"


@pytest.mark.django_db
def test_boolean_field_value_comes_back_as_a_bool() -> None:
    # Arrange
    instance = make_stub(is_active=False)

    # Act
    field, value = lookup_field("is_active", instance)
    assert field is not None
    display = display_for_field(value, field, "-")

    # Assert
    assert display is False


@pytest.mark.django_db
def test_property_value_resolves_through_lookup_field() -> None:
    # Arrange
    instance = make_stub(name="freddy")

    # Act
    field, value = lookup_field("display_name", instance)
    display = display_for_value(value, "-")

    # Assert
    assert field is None
    assert display == "FREDDY"


@pytest.mark.django_db
def test_method_value_resolves_through_lookup_field() -> None:
    # Arrange
    instance = make_stub(name="freddy", kind="a")

    # Act
    field, value = lookup_field("describe", instance)
    display = display_for_value(value, "-")

    # Assert
    assert field is None
    assert display == "freddy (a)"


@pytest.mark.django_db
def test_annotation_value_resolves_through_lookup_field() -> None:
    # Arrange
    make_stub(name="freddy")
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
    parent = make_stub(kind="b")
    child = make_stub_child(parent=parent)

    # Act
    field, value = lookup_field("parent__kind", child)
    assert field is not None
    display = display_for_field(value, field, "-")

    # Assert
    assert display == "Beta"


@pytest.mark.django_db
def test_missing_dunder_path_segment_returns_none_field_and_value() -> None:
    # Arrange
    parent = make_stub()
    child = make_stub_child(parent=parent)

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
        pytest.param(lambda: ("name", make_stub(name="parity")), id="plain_field"),
        pytest.param(lambda: ("kind", make_stub(kind="a")), id="choices_field"),
        pytest.param(
            lambda: ("sat_score", make_stub(sat_score=None)), id="empty_field"
        ),
        pytest.param(lambda: ("sat_score", make_stub(sat_score=1400)), id="int_field"),
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
    instance = make_stub(is_active=True)
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


# Tests for cotton/data-table-cells/link.html's quick_view column key.


LINK_CELL_URL_NAME = "panel_framework_test:framework"


def test_a_quick_view_column_renders_the_trigger_attributes() -> None:
    row = StubModel(pk=1, name="Ada")
    column = {
        "url_name": LINK_CELL_URL_NAME,
        "url_path_template": "stubs/{pk}",
        "text_attr": "name",
        "quick_view": True,
    }

    html = render_to_string(
        "cotton/data-table-cells/link.html", {"object": row, "column": column}
    )

    assert 'hx-get="/test-panel/framework/stubs/1/__quick-view"' in html
    assert 'aria-controls="quick-view"' in html
    assert 'aria-expanded="false"' in html
    # The drawer's title comes only from the frame it loads, so it can never
    # disagree with what a cell happens to show.
    assert "data-quick-view-title" not in html
    assert 'hx-sync="#quick-view-body:replace"' in html


def test_a_column_without_quick_view_renders_a_plain_link() -> None:
    row = StubModel(pk=1, name="Ada")
    column = {
        "url_name": LINK_CELL_URL_NAME,
        "url_path_template": "stubs/{pk}",
        "text_attr": "name",
    }

    html = render_to_string(
        "cotton/data-table-cells/link.html", {"object": row, "column": column}
    )

    assert 'href="/test-panel/framework/stubs/1"' in html
    assert "hx-get" not in html
    assert "aria-controls" not in html


def test_a_blank_text_attr_renders_the_placeholder_without_a_link() -> None:
    row = StubModel(pk=1, name="")
    column = {
        "url_name": LINK_CELL_URL_NAME,
        "url_path_template": "stubs/{pk}",
        "text_attr": "name",
        "quick_view": True,
    }

    html = render_to_string(
        "cotton/data-table-cells/link.html", {"object": row, "column": column}
    )

    assert html.strip() == "-"
    assert "<a" not in html
    assert "hx-get" not in html


def test_a_column_without_quick_view_keeps_its_htmx_nav_link() -> None:
    row = StubModel(pk=1, name="Ada")
    column = {
        "url_name": LINK_CELL_URL_NAME,
        "url_path_template": "stubs/{pk}",
        "text_attr": "name",
        "htmx_nav": True,
    }

    html = render_to_string(
        "cotton/data-table-cells/link.html", {"object": row, "column": column}
    )

    assert 'hx-get="/test-panel/framework/stubs/1"' in html
    assert 'hx-target="#main-content"' in html
    assert "aria-controls" not in html


def test_a_quick_view_column_renders_the_name_as_a_link_to_the_page() -> None:
    row = StubModel(pk=1, name="Ada")
    column = {
        "url_name": LINK_CELL_URL_NAME,
        "url_path_template": "stubs/{pk}",
        "text_attr": "name",
        "quick_view": True,
        "htmx_nav": True,
    }

    html = render_to_string(
        "cotton/data-table-cells/link.html", {"object": row, "column": column}
    )

    document = lxml.html.fromstring(f"<div>{html}</div>")
    (name_link,) = [
        a for a in document.cssselect("a") if a.text_content().strip() == "Ada"
    ]
    assert name_link.get("href") == "/test-panel/framework/stubs/1"
    assert name_link.get("hx-get") == "/test-panel/framework/stubs/1"
    assert name_link.get("hx-target") == "#main-content"
    assert name_link.get("aria-controls") is None


def test_a_quick_view_column_renders_a_labelled_icon_trigger_beside_the_name() -> None:
    row = StubModel(pk=1, name="Ada")
    column = {
        "url_name": LINK_CELL_URL_NAME,
        "url_path_template": "stubs/{pk}",
        "text_attr": "name",
        "quick_view": True,
    }

    html = render_to_string(
        "cotton/data-table-cells/link.html", {"object": row, "column": column}
    )

    document = lxml.html.fromstring(f"<div>{html}</div>")
    (trigger,) = document.cssselect('[aria-controls="quick-view"]')
    assert trigger.get("aria-label") == "Quick view: Ada"
    assert trigger.get("hx-get") == "/test-panel/framework/stubs/1/__quick-view"
    assert trigger.cssselect("svg")
    assert "Ada" not in trigger.text_content()
    links = document.cssselect("a")
    assert links.index(trigger) == len(links) - 1


def test_the_quick_view_trigger_shows_the_quick_view_icon() -> None:
    row = StubModel(pk=1, name="Ada")
    column = {
        "url_name": LINK_CELL_URL_NAME,
        "url_path_template": "stubs/{pk}",
        "text_attr": "name",
        "quick_view": True,
    }

    html = render_to_string(
        "cotton/data-table-cells/link.html", {"object": row, "column": column}
    )

    document = lxml.html.fromstring(f"<div>{html}</div>")
    (trigger,) = document.cssselect('[aria-controls="quick-view"]')
    (icon,) = trigger.cssselect("svg")
    assert icon.get("aria-label") == "quick_view"
