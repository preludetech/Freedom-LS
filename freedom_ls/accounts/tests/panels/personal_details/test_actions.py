"""Tests for the Personal details actions, through the test client."""

from __future__ import annotations

import re

import pytest

from django.apps import apps
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.panels.personal_details.actions import (
    ACCOUNT_CHANGED,
    CHANGE_OWN_NAME,
    CHANGE_OWN_PROFILE_PICTURE,
    REMOVE_OWN_PROFILE_PICTURE,
    EditNameAction,
    RemoveProfilePictureAction,
    UploadProfilePictureAction,
)
from freedom_ls.accounts.tests.profile_picture_samples import jpeg_bytes
from freedom_ls.accounts.validators import WRONG_TYPE

pytestmark = pytest.mark.django_db

EDIT_NAME_URL = "/accounts/profile/personal-details/__panels/name/__actions/edit_name"
PICTURE_PANEL_URL = "/accounts/profile/personal-details/__panels/profile-picture"
UPLOAD_PICTURE_URL = f"{PICTURE_PANEL_URL}/__actions/upload_profile_picture"
REMOVE_PICTURE_URL = f"{PICTURE_PANEL_URL}/__actions/remove_profile_picture"


@pytest.fixture
def signed_in(mock_site_context):
    user = UserFactory(first_name="Ada", last_name="Lovelace")
    client = Client()
    client.force_login(user)
    return client, user


def test_a_valid_save_stores_the_names_and_re_renders_the_form_with_them(signed_in):
    client, user = signed_in

    response = client.post(
        EDIT_NAME_URL,
        {"first_name": "Grace", "last_name": "Hopper"},
        headers={"HX-Request": "true"},
    )

    user.refresh_from_db()
    html = response.content.decode()
    assert response.status_code == 200
    assert (user.first_name, user.last_name) == ("Grace", "Hopper")
    assert 'value="Grace"' in html
    assert 'value="Hopper"' in html
    assert "Name saved" in html


def test_a_name_save_does_not_refresh_the_picture_panel(signed_in):
    client, _ = signed_in

    response = client.post(
        EDIT_NAME_URL,
        {"first_name": "Grace", "last_name": "Hopper"},
        headers={"HX-Request": "true"},
    )

    assert ACCOUNT_CHANGED not in response["HX-Trigger"]


def test_a_name_save_swaps_the_picture_preview_with_the_new_initials(signed_in):
    client, _ = signed_in

    response = client.post(
        EDIT_NAME_URL,
        {"first_name": "Grace", "last_name": "Hopper"},
        headers={"HX-Request": "true"},
    )

    preview = response.content.decode().split('id="account-picture-preview"')[1]
    assert preview.startswith(' hx-swap-oob="true"')
    assert "GH" in preview


def test_blank_names_are_accepted_and_stored_blank(signed_in):
    client, user = signed_in

    response = client.post(EDIT_NAME_URL, {"first_name": "", "last_name": ""})

    user.refresh_from_db()
    assert response.status_code == 200
    assert (user.first_name, user.last_name) == ("", "")


def test_a_first_name_over_200_characters_answers_422_and_stores_nothing(signed_in):
    client, user = signed_in

    response = client.post(
        EDIT_NAME_URL, {"first_name": "A" * 201, "last_name": "Hopper"}
    )

    user.refresh_from_db()
    html = response.content.decode()
    assert response.status_code == 422
    assert (user.first_name, user.last_name) == ("Ada", "Lovelace")
    assert len(re.findall(r'role="alert"', html)) == 1
    assert 'aria-invalid="true"' in html


def test_a_name_save_writes_no_audit_entry(signed_in):
    client, _ = signed_in
    audit_entries = apps.get_model(
        "freedom_ls_audit_log", "AuditLogEntry"
    )._base_manager
    before = audit_entries.count()

    client.post(EDIT_NAME_URL, {"first_name": "Grace", "last_name": "Hopper"})

    assert audit_entries.count() == before


def test_an_anonymous_save_redirects_to_login(mock_site_context):
    response = Client().post(EDIT_NAME_URL, {"first_name": "Grace"})

    assert response.status_code == 302
    assert reverse("account_login") in response.url


def test_the_edit_name_action_needs_the_change_own_name_capability(
    mock_site_context,
):
    action = EditNameAction(UserFactory())

    assert action.get_capability(None) == CHANGE_OWN_NAME


def test_a_valid_jpeg_is_stored_as_webp_and_the_superseded_file_is_deleted_on_commit(
    mock_site_context,
    pathless_profile_picture_storage,
    django_capture_on_commit_callbacks,
):
    user = UserFactory(with_profile_picture=True)
    old_name = user.profile_picture.name
    storage = user.profile_picture.storage
    client = Client()
    client.force_login(user)

    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(
            UPLOAD_PICTURE_URL,
            {"profile_picture": SimpleUploadedFile("me.jpg", jpeg_bytes())},
            headers={"HX-Request": "true"},
        )

    user.refresh_from_db()
    assert response.status_code == 200
    assert user.profile_picture.name.endswith(".webp")
    assert user.profile_picture.name != old_name
    assert storage.exists(old_name) is False
    assert "Profile picture saved" in response.content.decode()
    assert ACCOUNT_CHANGED in response["HX-Trigger"]


def test_a_refused_file_answers_422_with_the_error_and_keeps_the_stored_picture(
    mock_site_context, pathless_profile_picture_storage
):
    user = UserFactory(with_profile_picture=True)
    stored_name = user.profile_picture.name
    client = Client()
    client.force_login(user)

    response = client.post(
        UPLOAD_PICTURE_URL,
        {"profile_picture": SimpleUploadedFile("me.png", b"not an image")},
    )
    panel = client.get(PICTURE_PANEL_URL)

    user.refresh_from_db()
    assert response.status_code == 422
    assert WRONG_TYPE in response.content.decode()
    assert user.profile_picture.name == stored_name
    assert f'src="{user.profile_picture_url}"' in panel.content.decode()


def test_an_anonymous_picture_upload_redirects_to_login(mock_site_context):
    response = Client().post(UPLOAD_PICTURE_URL)

    assert response.status_code == 302
    assert reverse("account_login") in response.url


def test_the_upload_action_needs_the_change_own_profile_picture_capability(
    mock_site_context,
):
    action = UploadProfilePictureAction(UserFactory())

    assert action.get_capability(None) == CHANGE_OWN_PROFILE_PICTURE


def test_the_remove_trigger_is_absent_without_a_picture(signed_in):
    client, _ = signed_in

    response = client.get(PICTURE_PANEL_URL)

    assert REMOVE_PICTURE_URL not in response.content.decode()


def test_the_remove_trigger_is_present_with_a_picture(
    mock_site_context, pathless_profile_picture_storage
):
    user = UserFactory(with_profile_picture=True)
    client = Client()
    client.force_login(user)

    response = client.get(PICTURE_PANEL_URL)

    assert REMOVE_PICTURE_URL in response.content.decode()


def test_the_remove_dialog_has_an_error_tone_confirm_button_and_names_the_picture(
    mock_site_context, pathless_profile_picture_storage
):
    user = UserFactory(with_profile_picture=True)
    client = Client()
    client.force_login(user)

    response = client.get(REMOVE_PICTURE_URL)

    html = response.content.decode()
    assert response.status_code == 200
    assert "Remove your profile picture?" in html
    assert "Your current picture will be deleted" in html
    assert "btn-error" in html
    assert "Removing…" in html


def test_a_confirmed_removal_deletes_the_file_and_closes_the_dialog(
    mock_site_context,
    pathless_profile_picture_storage,
    django_capture_on_commit_callbacks,
):
    user = UserFactory(with_profile_picture=True)
    stored_name = user.profile_picture.name
    storage = user.profile_picture.storage
    client = Client()
    client.force_login(user)

    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(REMOVE_PICTURE_URL, headers={"HX-Request": "true"})

    user.refresh_from_db()
    assert response.status_code == 200
    assert user.profile_picture.name == ""
    assert storage.exists(stored_name) is False
    assert "closeModal" in response["HX-Trigger"]
    assert ACCOUNT_CHANGED in response["HX-Trigger"]
    assert "Profile picture removed" in response.content.decode()
    assert (response["HX-Retarget"], response["HX-Reswap"]) == ("body", "none")


def test_the_remove_action_needs_the_remove_own_profile_picture_capability(
    mock_site_context,
):
    action = RemoveProfilePictureAction()

    assert action.get_capability(None) == REMOVE_OWN_PROFILE_PICTURE


def test_a_name_save_swaps_the_header_avatar_with_the_new_initials_and_name(
    signed_in,
):
    client, _ = signed_in

    response = client.post(
        EDIT_NAME_URL,
        {"first_name": "Grace", "last_name": "Hopper"},
        headers={"HX-Request": "true"},
    )

    html = response.content.decode()
    assert 'id="header-avatar"' in html
    assert 'hx-swap-oob="true"' in html
    assert "GH" in html
    assert "Open user menu for Grace Hopper" in html


def test_an_upload_swaps_the_header_avatar_with_the_new_picture(
    mock_site_context, pathless_profile_picture_storage
):
    user = UserFactory()
    client = Client()
    client.force_login(user)

    response = client.post(
        UPLOAD_PICTURE_URL,
        {"profile_picture": SimpleUploadedFile("me.jpg", jpeg_bytes())},
        headers={"HX-Request": "true"},
    )

    user.refresh_from_db()
    html = response.content.decode()
    assert 'id="header-avatar"' in html
    assert f'src="{user.profile_picture_url}"' in html.split('id="header-avatar"')[1]


def test_a_removal_swaps_the_header_avatar_back_to_initials(
    mock_site_context, pathless_profile_picture_storage
):
    user = UserFactory(
        with_profile_picture=True, first_name="Ada", last_name="Lovelace"
    )
    client = Client()
    client.force_login(user)

    response = client.post(REMOVE_PICTURE_URL, headers={"HX-Request": "true"})

    avatar = response.content.decode().split('id="header-avatar"')[1]
    assert "AL" in avatar
    assert "data-profile-picture" not in avatar
