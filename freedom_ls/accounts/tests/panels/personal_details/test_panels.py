"""Tests for the panels on the Personal details page."""

from __future__ import annotations

import re

import pytest

from django.contrib.sites.models import Site
from django.test import Client

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.panels.personal_details.config import PersonalDetailsConfig
from freedom_ls.accounts.panels.personal_details.panels import ProfilePicturePanel
from freedom_ls.panel_framework.context import PanelContext

pytestmark = pytest.mark.django_db

PICTURE_PANEL_URL = "/accounts/profile/personal-details/__panels/profile-picture"


@pytest.fixture
def picture_panel_html(mock_site_context: Site) -> str:
    client = Client()
    client.force_login(UserFactory())
    return client.get(PICTURE_PANEL_URL).content.decode()


def test_the_picture_form_renders_the_help_text_the_input_points_at(
    picture_panel_html,
):
    assert 'id="id_profile_picture_helptext"' in picture_panel_html
    assert re.search(
        r'<input[^>]*aria-describedby="[^"]*id_profile_picture_helptext',
        picture_panel_html,
    )


def test_the_picture_form_accepts_images_posts_multipart_and_offers_no_removal(
    picture_panel_html,
):
    assert 'accept="image/jpeg,image/png,image/webp"' in picture_panel_html
    assert 'enctype="multipart/form-data"' in picture_panel_html
    assert "remove_profile_picture" not in picture_panel_html


def test_the_preview_reads_the_stored_picture_after_a_refused_file_is_bound(
    mock_site_context, pathless_profile_picture_storage, rf
):
    user = UserFactory(with_profile_picture=True)
    stored_url = user.profile_picture_url
    request = rf.get(PICTURE_PANEL_URL)
    request.user = user
    bound_instance = type(user)._base_manager.get(pk=user.pk)
    bound_instance.profile_picture = "profile_pictures/refused.webp"
    ctx = PanelContext(
        request=request,
        instance=bound_instance,
        base_url=PICTURE_PANEL_URL,
        name="profile-picture",
        config=PersonalDetailsConfig,
    )

    context = ProfilePicturePanel(ctx).get_context_data()

    assert context["stored_user"].profile_picture_url == stored_url
