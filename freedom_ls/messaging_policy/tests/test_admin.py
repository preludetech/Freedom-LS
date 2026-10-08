from __future__ import annotations

import html

import pytest

from django.contrib.sites.models import Site
from django.test import Client
from django.urls import reverse

from freedom_ls.messaging_policy.factories import SiteMessagingConfigFactory
from freedom_ls.messaging_policy.models import FLAG_NAMES, SiteMessagingConfig

pytestmark = pytest.mark.django_db

ADD_URL = "admin:freedom_ls_messaging_policy_sitemessagingconfig_add"
CHANGELIST_URL = "admin:freedom_ls_messaging_policy_sitemessagingconfig_changelist"
POST_DATA = {
    "learner_to_educator": "open",
    "learner_to_cohort_peer": "closed",
    "learner_to_course_peer": "inherit",
}


def test_the_add_page_shows_the_flags_and_no_site_field(
    staff_client: Client,
) -> None:
    response = staff_client.get(reverse(ADD_URL))

    content = response.content.decode()
    assert response.status_code == 200
    assert all(f'name="{flag}"' in content for flag in FLAG_NAMES)
    assert 'name="site"' not in content


def test_the_add_page_shows_the_flag_help_text(staff_client: Client) -> None:
    response = staff_client.get(reverse(ADD_URL))

    assert '"Inherit" uses the next level up.' in html.unescape(
        response.content.decode()
    )


def test_a_post_creates_the_row_for_the_site(
    staff_client: Client, mock_site_context: Site
) -> None:
    response = staff_client.post(reverse(ADD_URL), POST_DATA)

    assert response.status_code == 302
    config = SiteMessagingConfig.objects.get()
    assert config.site == mock_site_context
    assert config.learner_to_educator == "open"


def test_the_changelist_shows_the_flags(staff_client: Client) -> None:
    SiteMessagingConfigFactory(learner_to_educator="open")

    response = staff_client.get(reverse(CHANGELIST_URL))

    content = response.content.decode()
    assert response.status_code == 200
    assert all(f"field-{flag}" in content for flag in FLAG_NAMES)


def test_a_second_post_for_the_site_is_a_form_error(staff_client: Client) -> None:
    SiteMessagingConfigFactory()

    response = staff_client.post(reverse(ADD_URL), POST_DATA)

    assert response.status_code == 200
    assert response.context["adminform"].form.non_field_errors()
    assert SiteMessagingConfig.objects.count() == 1
