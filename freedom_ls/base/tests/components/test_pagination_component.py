"""Tests for the <c-pagination /> cotton component."""

from __future__ import annotations

from django_cotton.compiler_regex import CottonCompiler

from django.core.paginator import Paginator
from django.template import Context, Template
from django.test import RequestFactory

_cotton_compiler = CottonCompiler()


def _render(template_string: str, **context_kwargs: object) -> str:
    processed = _cotton_compiler.process(template_string)
    template = Template(processed)
    return template.render(Context(context_kwargs))


def _page(page_number: int, num_pages: int, per_page: int = 1) -> object:
    """Build a ``Page`` object with ``num_pages`` total pages."""
    object_list = list(range(num_pages * per_page))
    paginator = Paginator(object_list, per_page)
    return paginator.get_page(page_number)


_BASE = (
    '<c-pagination :page_obj="page_obj" base_url="/items/" table_id="my-table" '
    "{extras} />"
)


class TestPaginationComponent:
    def test_renders_nothing_when_only_one_page(self) -> None:
        result = _render(_BASE.format(extras=""), page_obj=_page(1, 1))
        # No pagination links should render
        assert "?page=" not in result
        assert "Next" not in result

    def test_renders_numbered_links_for_multiple_pages(self) -> None:
        result = _render(_BASE.format(extras=""), page_obj=_page(2, 3))
        assert "?page=1" in result
        assert "?page=3" in result
        assert 'hx-target="#my-table"' in result

    def test_preserves_sort_search_params_in_links(self) -> None:
        template = (
            '<c-pagination :page_obj="page_obj" base_url="/items/" table_id="my-table" '
            'sort_by="name" sort_order="asc" search_query="alice" />'
        )
        result = _render(template, page_obj=_page(2, 3))
        assert "sort=name" in result
        assert "order=asc" in result
        assert "search=alice" in result

    def test_preserves_extra_params_in_links(self) -> None:
        template = (
            '<c-pagination :page_obj="page_obj" base_url="/items/" table_id="my-table" '
            'extra_params="registration=abc&col_page=2" />'
        )
        result = _render(template, page_obj=_page(2, 3))
        assert "registration=abc" in result
        assert "col_page=2" in result

    def test_uses_table_id_as_hx_target(self) -> None:
        result = _render(_BASE.format(extras=""), page_obj=_page(2, 3))
        assert 'hx-target="#my-table"' in result

    def test_combines_sort_search_and_extra_params(self) -> None:
        """All three optional input groups must coexist in a single link."""
        template = (
            '<c-pagination :page_obj="page_obj" base_url="/items/" table_id="my-table" '
            'sort_by="name" sort_order="asc" search_query="alice" '
            'extra_params="registration=abc" />'
        )
        result = _render(template, page_obj=_page(2, 3))
        assert "sort=name" in result
        assert "order=asc" in result
        assert "search=alice" in result
        assert "registration=abc" in result

    def test_url_encodes_special_characters_in_search(self) -> None:
        """Search terms with ``&`` must be encoded so they don't break the URL."""
        template = (
            '<c-pagination :page_obj="page_obj" base_url="/items/" table_id="my-table" '
            'search_query="a & b" />'
        )
        result = _render(template, page_obj=_page(2, 3))
        # URL-encoded "a & b" is "a+%26+b" (urlencode form) or "a%20%26%20b"
        # — accept either by checking the raw "&" wasn't passed through.
        assert "search=a & b" not in result
        assert "%26" in result

    def test_renders_first_and_last_links_when_paginator_has_many_pages(self) -> None:
        result = _render(_BASE.format(extras=""), page_obj=_page(5, 10))
        # First page link
        assert "?page=1" in result
        # Last page link
        assert "?page=10" in result
        assert "First" in result
        assert "Last" in result

    def test_links_do_not_push_the_url_by_default(self) -> None:
        result = _render(_BASE.format(extras=""), page_obj=_page(2, 3))
        assert "hx-push-url" not in result

    def test_every_link_pushes_the_url_when_push_url_is_set(self) -> None:
        result = _render(_BASE.format(extras='push_url="true"'), page_obj=_page(2, 3))
        assert result.count("hx-get=") == result.count('hx-push-url="true"')
        assert result.count("hx-get=") > 0

    def test_renders_from_links_with_page_url_and_preserves_other_params(self) -> None:
        """When ``links`` is passed, hrefs are built from ``page_url`` and
        ``hx-get`` from ``base_url``, both keeping every other request param."""
        request = RequestFactory().get("/panel/", {"other": "1"})
        links = {
            "previous": None,
            "next": None,
            "pages": [{"number": 3, "changes": {"t-page": 3}, "current": False}],
        }
        template = (
            '<c-pagination :page_obj="page_obj" base_url="/panel/" page_url="/items/" '
            ':links="links" table_id="my-table" />'
        )

        result = _render(template, page_obj=_page(2, 3), links=links, request=request)

        assert 'href="/items/?' in result
        assert 'hx-get="/panel/?' in result
        assert "t-page=3" in result
        assert "other=1" in result
