"""The QA organisations command seeds both branches of the organisation mark."""

from __future__ import annotations

import pytest

from django.contrib.sites.models import Site
from django.core.management import call_command

from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.qa_helpers"):
    pytest.skip("qa_helpers not installed", allow_module_level=True)

from freedom_ls.organisations.models import Organisation
from freedom_ls.qa_helpers.management.commands.qa_create_organisations import (
    WIDE_LOGO_NAME,
    WITH_PROFILE_LOGO_NAME,
)

pytestmark = [pytest.mark.django_db, pytest.mark.dev_tooling]


@pytest.fixture
def qa_site(mock_site_context) -> Site:
    site: Site = Site.objects.get_current()
    site.name = "DemoDev"
    site.save()
    return site


@pytest.fixture
def seeded_site(qa_site: Site) -> Site:
    call_command("qa_create_organisations", "DemoDev")
    call_command("qa_create_organisations", "DemoDev")
    return qa_site


@pytest.mark.parametrize("name", [WITH_PROFILE_LOGO_NAME, WIDE_LOGO_NAME])
def test_running_twice_leaves_one_organisation_per_name(seeded_site, name):
    assert Organisation.objects.filter(site=seeded_site, name=name).count() == 1


def test_profile_logo_organisation_has_a_profile_logo(seeded_site):
    organisation = Organisation.objects.get(
        site=seeded_site, name=WITH_PROFILE_LOGO_NAME
    )

    assert organisation.profile_logo


def test_profile_logo_organisation_has_a_bio(seeded_site):
    organisation = Organisation.objects.get(
        site=seeded_site, name=WITH_PROFILE_LOGO_NAME
    )

    assert organisation.bio


def test_wide_logo_organisation_has_a_logo(seeded_site):
    organisation = Organisation.objects.get(site=seeded_site, name=WIDE_LOGO_NAME)

    assert organisation.logo


def test_wide_logo_organisation_has_no_profile_logo(seeded_site):
    organisation = Organisation.objects.get(site=seeded_site, name=WIDE_LOGO_NAME)

    assert not organisation.profile_logo


def test_wide_logo_organisation_has_no_bio(seeded_site):
    organisation = Organisation.objects.get(site=seeded_site, name=WIDE_LOGO_NAME)

    assert organisation.bio == ""
