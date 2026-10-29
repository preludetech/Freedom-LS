"""Tests for the <c-organisation-mark /> cotton component."""

import pytest
from django_cotton.compiler_regex import CottonCompiler

from django.core.files.uploadedfile import SimpleUploadedFile
from django.template import Context, Template

from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation

_cotton_compiler = CottonCompiler()

_ONE_PIXEL_GIF = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00"
    b"\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
)


def _gif(name: str) -> SimpleUploadedFile:
    return SimpleUploadedFile(name, _ONE_PIXEL_GIF, content_type="image/gif")


def _render(organisation: Organisation) -> str:
    processed = _cotton_compiler.process(
        '<c-organisation-mark :organisation="organisation" />'
    )
    return Template(processed).render(Context({"organisation": organisation}))


@pytest.mark.django_db
def test_profile_logo_wins_over_the_logo_and_is_cropped_to_the_circle(
    mock_site_context,
):
    organisation = OrganisationFactory(
        logo=_gif("logo.gif"), profile_logo=_gif("profile.gif")
    )

    result = _render(organisation)

    assert result.count("<img") == 1
    assert f'src="{organisation.profile_logo.url}"' in result
    assert "object-cover" in result


@pytest.mark.django_db
def test_logo_alone_is_contained_not_cropped(mock_site_context):
    organisation = OrganisationFactory(logo=_gif("logo.gif"))

    result = _render(organisation)

    assert f'src="{organisation.logo.url}"' in result
    assert "object-contain" in result


@pytest.mark.django_db
def test_initials_are_hidden_from_assistive_technology_without_a_logo(
    mock_site_context,
):
    organisation = OrganisationFactory(name="Acme Academy")

    result = _render(organisation)

    assert "<img" not in result
    assert 'aria-hidden="true"' in result
    assert "AA" in result


@pytest.mark.django_db
def test_a_name_with_no_letters_renders_the_unknown_icon(mock_site_context):
    organisation = OrganisationFactory(name="1234")

    result = _render(organisation)

    assert "<img" not in result
    assert "<svg" in result


@pytest.mark.django_db
@pytest.mark.parametrize("field_name", ["logo", "profile_logo"])
def test_logo_images_are_decorative(mock_site_context, field_name):
    organisation = OrganisationFactory(**{field_name: _gif("image.gif")})

    assert 'alt=""' in _render(organisation)
