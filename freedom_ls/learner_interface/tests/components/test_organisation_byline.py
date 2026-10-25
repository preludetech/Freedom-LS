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
def test_renders_the_logo_and_the_name(mock_site_context):
    organisation = OrganisationFactory(
        name="Acme Academy",
        logo=SimpleUploadedFile("logo.gif", _ONE_PIXEL_GIF, content_type="image/gif"),
    )

    result = _render(organisation)

    assert "Acme Academy" in result
    assert "<img" in result
    assert 'alt=""' in result


@pytest.mark.django_db
def test_renders_the_name_only_without_a_logo(mock_site_context):
    organisation = OrganisationFactory(name="Acme Academy")

    result = _render(organisation)

    assert "Acme Academy" in result
    assert "<img" not in result


@pytest.mark.django_db
def test_renders_nothing_for_the_default_organisation(mock_site_context):
    organisation = get_default_organisation(mock_site_context)

    assert _render(organisation).strip() == ""


def test_renders_nothing_for_an_empty_value():
    assert _render(None).strip() == ""
