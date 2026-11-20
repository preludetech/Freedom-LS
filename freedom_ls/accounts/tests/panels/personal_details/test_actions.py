"""Tests for the Personal details actions, through the test client."""

from __future__ import annotations

import re
from typing import cast

import lxml.html
import pytest
from allauth.account.models import EmailAddress

from django.contrib.sites.models import Site
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.forms import NO_PICTURE_CHOSEN
from freedom_ls.accounts.models import User
from freedom_ls.accounts.panels.personal_details.actions import (
    ACCOUNT_CHANGED,
    CHANGE_OWN_NAME,
    CHANGE_OWN_PROFILE_PICTURE,
    EMAIL_ADDRESSES_CHANGED,
    PASSWORD_CHANGED,
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
def signed_in(mock_site_context: Site) -> tuple[Client, User]:
    user = cast(User, UserFactory(first_name="Ada", last_name="Lovelace"))
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

    response = client.post(
        EDIT_NAME_URL,
        {"first_name": "", "last_name": ""},
        headers={"HX-Request": "true"},
    )

    user.refresh_from_db()
    assert response.status_code == 200
    assert (user.first_name, user.last_name) == ("", "")


def test_a_first_name_over_200_characters_answers_422_and_stores_nothing(signed_in):
    client, user = signed_in

    response = client.post(
        EDIT_NAME_URL,
        {"first_name": "A" * 201, "last_name": "Hopper"},
        headers={"HX-Request": "true"},
    )

    user.refresh_from_db()
    html = response.content.decode()
    assert response.status_code == 422
    assert (user.first_name, user.last_name) == ("Ada", "Lovelace")
    assert len(re.findall(r'role="alert"', html)) == 1
    assert 'aria-invalid="true"' in html


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
        headers={"HX-Request": "true"},
    )
    panel = client.get(PICTURE_PANEL_URL)

    user.refresh_from_db()
    assert response.status_code == 422
    assert WRONG_TYPE in response.content.decode()
    assert user.profile_picture.name == stored_name
    assert f'src="{user.profile_picture_url}"' in panel.content.decode()


def test_a_picture_save_with_no_file_answers_422_and_reports_no_success(signed_in):
    client, _ = signed_in

    response = client.post(UPLOAD_PICTURE_URL, headers={"HX-Request": "true"})

    html = response.content.decode()
    assert response.status_code == 422
    assert NO_PICTURE_CHOSEN in html
    assert "Profile picture saved" not in html


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


PERSONAL_DETAILS_URL = "/accounts/profile/personal-details"


@pytest.mark.parametrize(
    ("form_id", "action_url"),
    [
        ("account-name-form", EDIT_NAME_URL),
        ("account-picture-form", UPLOAD_PICTURE_URL),
    ],
)
def test_each_form_on_the_page_can_post_without_javascript(
    signed_in, form_id, action_url
):
    client, _ = signed_in

    page = lxml.html.fromstring(client.get(PERSONAL_DETAILS_URL).content.decode())

    (form,) = page.xpath(f"//form[@id='{form_id}']")
    assert (form.get("method"), form.get("action")) == ("post", action_url)
    assert len(form.xpath(".//input[@name='csrfmiddlewaretoken']")) == 1


def test_a_plain_name_post_saves_and_redirects_to_the_page(signed_in):
    client, user = signed_in

    response = client.post(
        EDIT_NAME_URL, {"first_name": "Grace", "last_name": "Hopper"}
    )

    user.refresh_from_db()
    assert (response.status_code, response["Location"]) == (303, PERSONAL_DETAILS_URL)
    assert (user.first_name, user.last_name) == ("Grace", "Hopper")


def test_a_refused_plain_name_post_redirects_with_the_error_as_a_flash(signed_in):
    client, user = signed_in

    response = client.post(
        EDIT_NAME_URL, {"first_name": "A" * 201, "last_name": "Hopper"}, follow=True
    )

    user.refresh_from_db()
    assert response.redirect_chain == [(PERSONAL_DETAILS_URL, 303)]
    assert user.first_name == "Ada"
    assert "First name: " in response.content.decode()


def test_a_plain_picture_post_saves_and_redirects_to_the_page(
    mock_site_context, pathless_profile_picture_storage
):
    user = UserFactory()
    client = Client()
    client.force_login(user)

    response = client.post(
        UPLOAD_PICTURE_URL,
        {"profile_picture": SimpleUploadedFile("me.jpg", jpeg_bytes())},
    )

    user.refresh_from_db()
    assert (response.status_code, response["Location"]) == (303, PERSONAL_DETAILS_URL)
    assert user.profile_picture.name.endswith(".webp")


PAGE_URL = "/accounts/profile/personal-details"
EMAIL_PANEL_URL = f"{PAGE_URL}/__panels/email-addresses"
ADD_EMAIL_URL = f"{EMAIL_PANEL_URL}/__actions/add_email"
MAKE_PRIMARY_URL = f"{EMAIL_PANEL_URL}/__actions/make_primary_email"
RESEND_URL = f"{EMAIL_PANEL_URL}/__actions/resend_email_verification"
REMOVE_EMAIL_URL = f"{EMAIL_PANEL_URL}/__actions/remove_email"
CHANGE_PASSWORD_URL = f"{PAGE_URL}/__panels/password/__actions/change_password"
OLD_PASSWORD = "an-old-long-passphrase-1"  # noqa: S105  # pragma: allowlist secret
NEW_PASSWORD = "a-new-long-passphrase-2"  # noqa: S105  # pragma: allowlist secret
HTMX = {"HX-Request": "true"}


@pytest.fixture
def with_addresses(
    signed_in: tuple[Client, User],
) -> tuple[Client, User, EmailAddress, EmailAddress]:
    client, user = signed_in
    primary, _ = EmailAddress.objects.update_or_create(
        user=user, email=user.email, defaults={"primary": True, "verified": True}
    )
    secondary = EmailAddress.objects.create(
        user=user, email="second@example.com", primary=False, verified=False
    )
    return client, user, primary, secondary


def _document(client: Client) -> lxml.html.HtmlElement:
    return lxml.html.fromstring(client.get(PAGE_URL).content.decode())


def test_the_page_stacks_the_email_addresses_and_password_panels(with_addresses):
    client, *_ = with_addresses

    names = [
        section.get("data-panel")
        for section in _document(client).cssselect("section[data-panel]")
    ]

    assert names[-2:] == ["email-addresses", "password"]


def test_each_address_is_a_row_with_its_own_actions_and_no_radio(with_addresses):
    client, _, primary, secondary = with_addresses

    panel = _document(client).cssselect('section[data-panel="email-addresses"]')[0]
    rows = {
        row.cssselect("span.font-medium")[0].text_content(): row
        for row in panel.cssselect('[data-testid="email-address-row"]')
    }

    assert panel.cssselect('input[type="radio"]') == []
    assert set(rows) == {primary.email, secondary.email}
    primary_text = rows[primary.email].text_content()
    assert "Primary" in primary_text
    assert "Verified" in primary_text
    assert "Remove" not in primary_text
    secondary_text = rows[secondary.email].text_content()
    assert "Unverified" in secondary_text
    assert "Resend verification" in secondary_text
    assert "Remove" in secondary_text


def test_add_email_sits_in_the_email_panel_footer(with_addresses):
    client, *_ = with_addresses

    panel = _document(client).cssselect('section[data-panel="email-addresses"]')[0]

    (trigger,) = panel.cssselect("footer button[hx-get]")
    assert trigger.get("hx-get").endswith("/__actions/add_email")


def test_adding_an_address_stores_it_unverified_and_sends_a_verification(
    with_addresses, mailoutbox
):
    client, user, *_ = with_addresses

    response = client.post(ADD_EMAIL_URL, {"email": "new@example.com"}, headers=HTMX)

    added = EmailAddress.objects.get(user=user, email="new@example.com")
    assert response.status_code == 200
    assert not added.verified
    assert len(mailoutbox) == 1
    assert EMAIL_ADDRESSES_CHANGED in response["HX-Trigger"]
    assert "closeModal" in response["HX-Trigger"]
    assert "new@example.com" in response.content.decode()


def test_adding_an_address_already_on_the_account_is_refused(with_addresses):
    client, _, _, secondary = with_addresses

    response = client.post(ADD_EMAIL_URL, {"email": secondary.email}, headers=HTMX)

    assert response.status_code == 422


def test_making_a_verified_address_primary_moves_the_primary(with_addresses):
    client, user, primary, secondary = with_addresses
    secondary.verified = True
    secondary.save()

    response = client.post(MAKE_PRIMARY_URL, {"email": secondary.pk}, headers=HTMX)

    secondary.refresh_from_db()
    primary.refresh_from_db()
    user.refresh_from_db()
    assert response.status_code == 200
    assert secondary.primary
    assert not primary.primary
    assert user.email == secondary.email
    assert EMAIL_ADDRESSES_CHANGED in response["HX-Trigger"]


def test_an_unverified_address_is_not_made_primary(with_addresses):
    client, _, primary, secondary = with_addresses

    client.post(MAKE_PRIMARY_URL, {"email": secondary.pk}, headers=HTMX)

    primary.refresh_from_db()
    assert primary.primary


def test_resending_a_verification_sends_an_email(with_addresses, mailoutbox):
    client, _, _, secondary = with_addresses

    response = client.post(RESEND_URL, {"email": secondary.pk}, headers=HTMX)

    assert response.status_code == 200
    assert [message.to for message in mailoutbox] == [[secondary.email]]


def test_the_remove_dialog_is_an_error_tone_confirmation_naming_the_address(
    with_addresses,
):
    client, _, _, secondary = with_addresses

    response = client.get(REMOVE_EMAIL_URL, {"email": secondary.pk}, headers=HTMX)

    html = response.content.decode()
    assert response.status_code == 200
    assert f"Remove {secondary.email}?" in html
    assert "btn-error" in html


def test_removing_a_secondary_address_deletes_it(with_addresses):
    client, _, _, secondary = with_addresses

    response = client.post(REMOVE_EMAIL_URL, {"email": secondary.pk}, headers=HTMX)

    assert response.status_code == 200
    assert not EmailAddress.objects.filter(pk=secondary.pk).exists()
    assert "closeModal" in response["HX-Trigger"]


def test_the_primary_address_is_not_removed(with_addresses):
    client, _, primary, _ = with_addresses

    client.post(REMOVE_EMAIL_URL, {"email": primary.pk}, headers=HTMX)

    assert EmailAddress.objects.filter(pk=primary.pk).exists()


@pytest.mark.parametrize("url", [MAKE_PRIMARY_URL, RESEND_URL, REMOVE_EMAIL_URL])
def test_another_users_address_is_not_found(with_addresses, url):
    client, *_ = with_addresses
    stranger = EmailAddress.objects.create(
        user=cast(User, UserFactory()), email="stranger@example.com", verified=True
    )

    response = client.post(url, {"email": stranger.pk}, headers=HTMX)

    assert response.status_code == 404
    assert EmailAddress.objects.filter(pk=stranger.pk).exists()


def test_the_manage_email_rate_limit_applies(with_addresses):
    client, _, _, secondary = with_addresses
    cache.clear()

    with override_settings(ACCOUNT_RATE_LIMITS={"manage_email": "1/m/user"}):
        client.post(RESEND_URL, {"email": secondary.pk}, headers=HTMX)
        response = client.post(RESEND_URL, {"email": secondary.pk}, headers=HTMX)

    assert response.status_code == 429


def _with_password(client: Client, user: User) -> None:
    user.set_password(OLD_PASSWORD)
    user.save()
    client.force_login(user)


def test_the_password_panel_has_its_submit_in_the_footer(signed_in):
    client, user = signed_in
    _with_password(client, user)

    panel = _document(client).cssselect('section[data-panel="password"]')[0]

    assert panel.cssselect("form#account-password-form button") == []
    (submit,) = panel.cssselect("footer button[type=submit]")
    assert submit.get("form") == "account-password-form"
    assert "Change password" in submit.text_content()
    assert panel.cssselect('a[href="/accounts/password/reset/"]')


def test_changing_the_password_keeps_the_session_signed_in(signed_in):
    client, user = signed_in
    _with_password(client, user)

    response = client.post(
        CHANGE_PASSWORD_URL,
        {
            "oldpassword": OLD_PASSWORD,
            "password1": NEW_PASSWORD,
            "password2": NEW_PASSWORD,
        },
        headers=HTMX,
    )

    user.refresh_from_db()
    assert response.status_code == 200
    assert user.check_password(NEW_PASSWORD)
    assert PASSWORD_CHANGED in response["HX-Trigger"]
    assert client.get(PAGE_URL).status_code == 200


def test_a_wrong_current_password_is_refused_under_its_field(signed_in):
    client, user = signed_in
    _with_password(client, user)

    response = client.post(
        CHANGE_PASSWORD_URL,
        {
            "oldpassword": "wrong-passphrase",  # pragma: allowlist secret
            "password1": NEW_PASSWORD,
            "password2": NEW_PASSWORD,
        },
        headers=HTMX,
    )

    user.refresh_from_db()
    assert response.status_code == 422
    assert user.check_password(OLD_PASSWORD)
    root = lxml.html.fromstring(response.content.decode())
    assert root.cssselect('p[role="alert"]#id_oldpassword_error')


def test_a_user_with_no_password_sets_one(signed_in):
    client, user = signed_in
    user.set_unusable_password()
    user.save()
    client.force_login(user)

    panel = _document(client).cssselect('section[data-panel="password"]')[0]
    assert "Set password" in panel.cssselect("h2")[0].text_content()

    response = client.post(
        CHANGE_PASSWORD_URL,
        {"password1": NEW_PASSWORD, "password2": NEW_PASSWORD},
        headers=HTMX,
    )

    user.refresh_from_db()
    assert response.status_code == 200
    assert user.check_password(NEW_PASSWORD)


def test_the_password_labels_are_in_sentence_case(signed_in):
    client, user = signed_in
    _with_password(client, user)

    panel = _document(client).cssselect('section[data-panel="password"]')[0]
    labels = [label.text_content() for label in panel.cssselect("label")]

    assert "Current password:" in labels
    assert "New password (again):" in labels
