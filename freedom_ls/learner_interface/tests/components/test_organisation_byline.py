"""Tests for the <c-organisation-byline /> cotton component."""

import pytest
from django_cotton.compiler_regex import CottonCompiler

from django.core.files.uploadedfile import SimpleUploadedFile
from django.template import Context, Template

from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.utils import get_default_organisation

_cotton_compiler = CottonCompiler()

_ONE_PIXEL_GIF = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00"
    b"\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
)


def _render(organisation: object) -> str:
    processed = _cotton_compiler.process(
        '<c-organisation-byline :organisation="organisation" />'
    )
    return Template(processed).render(Context({"organisation": organisation}))


@pytest.mark.django_db
def test_renders_the_name_beside_the_mark_with_a_title(mock_site_context):
    organisation = OrganisationFactory(name="Acme Academy")

    result = _render(organisation)

    assert "Acme Academy" in result
    assert 'title="Acme Academy"' in result
    assert 'data-testid="organisation-mark"' in result


@pytest.mark.django_db
def test_renders_the_monogram_when_there_is_no_logo(mock_site_context):
    organisation = OrganisationFactory(name="Acme Academy")

    result = _render(organisation)

    assert "<img" not in result
    assert "AA" in result


@pytest.mark.django_db
def test_renders_the_logo_image_as_decorative(mock_site_context):
    organisation = OrganisationFactory(
        name="Acme Academy",
        logo=SimpleUploadedFile("logo.gif", _ONE_PIXEL_GIF, content_type="image/gif"),
    )

    result = _render(organisation)

    assert "<img" in result
    assert 'alt=""' in result


@pytest.mark.django_db
def test_text_muted_is_dropped_when_a_class_is_passed(mock_site_context):
    organisation = OrganisationFactory(name="Acme Academy")
    processed = _cotton_compiler.process(
        '<c-organisation-byline :organisation="organisation" class="text-white" />'
    )

    result = Template(processed).render(Context({"organisation": organisation}))
    paragraph = result.split("<p", 1)[1].split(">", 1)[0]

    assert "text-white" in paragraph
    assert "text-muted" not in paragraph


@pytest.mark.django_db
def test_text_muted_applies_when_no_class_is_passed(mock_site_context):
    organisation = OrganisationFactory(name="Acme Academy")

    result = _render(organisation)

    assert "text-muted" in result.split("<p", 1)[1].split(">", 1)[0]


@pytest.mark.django_db
def test_renders_nothing_for_the_default_organisation(mock_site_context):
    organisation = get_default_organisation(mock_site_context)

    assert _render(organisation).strip() == ""


def test_renders_nothing_for_an_empty_value():
    assert _render(None).strip() == ""


def _render_overlap(organisation: object) -> str:
    processed = _cotton_compiler.process(
        '<c-organisation-byline :organisation="organisation" overlap="true" />'
    )
    return Template(processed).render(Context({"organisation": organisation}))


@pytest.mark.django_db
def test_overlap_pulls_a_raised_large_mark_up_over_the_card_header(
    mock_site_context,
):
    organisation = OrganisationFactory(name="Acme Academy")

    result = _render_overlap(organisation)
    paragraph = result.split("<p", 1)[1].split(">", 1)[0]

    assert "-mt-5" in paragraph
    assert "items-end" in paragraph
    assert "size-11" in result
    assert "ring-surface" in result


@pytest.mark.django_db
def test_overlap_renders_nothing_for_the_default_organisation(mock_site_context):
    organisation = get_default_organisation(mock_site_context)

    assert _render_overlap(organisation).strip() == ""
