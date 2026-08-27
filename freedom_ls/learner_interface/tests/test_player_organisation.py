"""The co-branding chip the resolved organisation feeds into the course
player's TOC header.

organisation_for_learner_course itself is tested next to the other query
helpers, in learner_management/tests/test_queries.py.
"""

from __future__ import annotations

import io

import lxml.html
import pytest
from PIL import Image

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.learner_management.factories import LearnerCourseRegistrationFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.utils import get_default_organisation


def _logo_upload(name: str = "logo.png") -> SimpleUploadedFile:
    buf = io.BytesIO()
    Image.new("RGB", (200, 100)).save(buf, format="PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


def _chip(response) -> str:
    """The rendered co-branding chip, on its own.

    Scoped to the element rather than searched across the whole player page,
    where decorative attributes such as aria-hidden appear on nearly every
    icon in the chrome and would satisfy the assertions by accident.
    """
    document = lxml.html.fromstring(response.content)
    elements = document.cssselect("#course-organisation-chip")
    assert elements, "no #course-organisation-chip in the response"
    return str(lxml.html.tostring(elements[0], encoding="unicode"))


@pytest.fixture
def player_response(mock_site_context, course_with_topic, logged_in_client):
    """The player's first item, for a learner registered through `organisation`."""

    def _get(organisation):
        course = course_with_topic()
        user = UserFactory()
        LearnerCourseRegistrationFactory(
            learner__user=user, collection=course, learner__organisation=organisation
        )
        response = logged_in_client(user).get(
            reverse(
                "learner_interface:view_course_item",
                kwargs={"course_slug": course.slug, "index": 1},
            )
        )
        assert response.status_code == 200
        response.course = course
        return response

    return _get


@pytest.mark.django_db
class TestCourseOrganisationChip:
    """The resolved organisation reaches the player's TOC header as a chip:
    the logo when there is one, an initials monogram otherwise, with the
    organisation's name rendered as text beside it."""

    def test_logo_renders_with_the_organisation_name(self, player_response):
        organisation = OrganisationFactory(name="Acme Corp", logo=_logo_upload())

        chip = _chip(player_response(organisation))

        assert organisation.logo.url in chip
        assert "Acme Corp" in chip

    def test_logo_is_decorative_because_the_name_is_already_text(self, player_response):
        """Labelling the mark as well would announce the organisation twice."""
        organisation = OrganisationFactory(name="Acme Corp", logo=_logo_upload())

        chip = _chip(player_response(organisation))

        assert 'alt=""' in chip

    def test_chip_renders_above_the_course_title(self, player_response):
        """Co-branding sits above the title, not below it. Compared as sibling
        order inside the outline header, so restyling either element does not
        change what this asserts."""
        organisation = OrganisationFactory(name="Acme Corp", logo=_logo_upload())

        response = player_response(organisation)

        document = lxml.html.fromstring(response.content)
        chip = document.cssselect("#course-organisation-chip")[0]
        header = chip.getparent()
        titles = [
            element
            for element in header.iterchildren("p")
            if (element.text or "").strip() == response.course.title
        ]
        assert titles, "no course-title paragraph in the outline header"
        siblings = list(header)
        assert siblings.index(chip) < siblings.index(titles[0])

    def test_initials_monogram_renders_when_organisation_has_no_logo(
        self, player_response
    ):
        organisation = OrganisationFactory(name="Beta School")

        chip = _chip(player_response(organisation))

        assert organisation.initials in chip
        assert "Beta School" in chip

    def test_monogram_is_hidden_from_assistive_technology(self, player_response):
        """It repeats the name rendered beside it."""
        organisation = OrganisationFactory(name="Beta School")

        chip = _chip(player_response(organisation))

        assert 'aria-hidden="true"' in chip

    def test_no_chip_for_the_sites_default_organisation(
        self, mock_site_context, player_response
    ):
        """The default organisation stands for the site itself, which the
        surrounding chrome already brands — co-branding it would repeat that."""
        organisation = get_default_organisation(mock_site_context)
        organisation.name = "Renamed Away From The Site"
        organisation.save()

        response = player_response(organisation)

        document = lxml.html.fromstring(response.content)
        assert not document.cssselect("#course-organisation-chip")
        assert "Renamed Away From The Site" not in response.content.decode()
