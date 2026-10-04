"""The educator interface's section configs and the pages they render."""

from __future__ import annotations

import lxml.html
import pytest

from django.test import Client
from django.urls import reverse

from freedom_ls.learner_management.factories import CohortFactory
from freedom_ls.organisations.factories import OrganisationFactory


@pytest.mark.django_db
def test_cohort_detail_page_shows_its_cards_directly_with_no_tab_strip(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation, name="Evening group")

    response = staff_client.get(
        reverse(
            "educator_interface:interface",
            kwargs={
                "organisation_slug": organisation.slug,
                "path_string": f"cohorts/{cohort.pk}",
            },
        )
    )

    document = lxml.html.fromstring(response.content.decode())
    headings = [h.text_content().strip() for h in document.cssselect("h2")]
    assert response.status_code == 200
    assert {"Details", "Course Registrations", "Learners"} <= set(headings)
    (region,) = document.cssselect("[data-tab-set]")
    assert not region.xpath("preceding-sibling::nav")
