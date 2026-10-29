"""The `document_title` tag."""

from __future__ import annotations

from django.template import Context, Engine


def _render(source: str, **context: str) -> str:
    return Engine.get_default().from_string(source).render(Context(context))


def test_document_title_puts_the_page_name_before_the_site_name():
    rendered = _render(
        "{% load base_tags %}{% document_title %}Body{% enddocument_title %}",
        site_name="Site",
    )

    assert rendered == "Body — Site"


def test_document_title_with_an_empty_body_is_the_site_name_alone():
    rendered = _render(
        "{% load base_tags %}{% document_title %}  {% enddocument_title %}",
        site_name="Site",
    )

    assert rendered == "Site"


def test_document_title_escapes_the_site_name():
    rendered = _render(
        "{% load base_tags %}{% document_title %}Body{% enddocument_title %}",
        site_name="A <b> & C",
    )

    assert rendered == "Body — A &lt;b&gt; &amp; C"


def test_document_title_body_can_be_overridden_by_a_child_block():
    engine = Engine(
        libraries={"base_tags": "freedom_ls.base.templatetags.base_tags"},
        loaders=[
            (
                "django.template.loaders.locmem.Loader",
                {
                    "parent.html": (
                        "{% load base_tags %}{% document_title %}"
                        "{% block head_title %}Parent{% endblock %}"
                        "{% enddocument_title %}"
                    ),
                    "child.html": (
                        '{% extends "parent.html" %}'
                        "{% block head_title %}Child{% endblock %}"
                    ),
                },
            )
        ],
    )

    rendered = engine.get_template("child.html").render(Context({"site_name": "Site"}))

    assert rendered == "Child — Site"
