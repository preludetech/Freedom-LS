"""Tests for the registration-completion view."""

from __future__ import annotations

import pytest

from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import SiteSignupPolicy

PHONE_FORM_PATH = "freedom_ls.accounts.tests._completion_view_fixtures.PhoneNumberForm"


@pytest.fixture
def authed_client(mock_site_context, db):
    user = UserFactory()
    client = Client()
    client.force_login(user)
    return client, user


@pytest.mark.django_db
def test_anonymous_user_redirected_to_login(mock_site_context):
    client = Client()
    response = client.get(reverse("accounts:complete_registration"))
    # login_required redirects to LOGIN_URL with a `next` parameter.
    assert response.status_code == 302
    assert "/accounts/login/" in response.url


@pytest.mark.django_db
def test_user_with_no_incomplete_forms_redirected(authed_client, site, settings):
    settings.LOGIN_REDIRECT_URL = "/"
    SiteSignupPolicy.objects.create(site=site, additional_registration_forms=[])
    client, _ = authed_client

    response = client.get(reverse("accounts:complete_registration"))

    assert response.status_code == 302
    assert response.url == "/"


@pytest.mark.django_db
def test_user_with_incomplete_forms_gets_200(authed_client, site):
    SiteSignupPolicy.objects.create(
        site=site, additional_registration_forms=[PHONE_FORM_PATH]
    )
    client, _ = authed_client

    response = client.get(reverse("accounts:complete_registration"))

    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "phone_number" in body  # field name leaks via id_for_label / name


@pytest.mark.django_db
def test_posting_valid_data_persists_and_redirects(authed_client, site, settings):
    """The form's `save(user)` must run with `request.user` and persist data."""
    settings.LOGIN_REDIRECT_URL = "/"
    SiteSignupPolicy.objects.create(
        site=site, additional_registration_forms=[PHONE_FORM_PATH]
    )
    client, user = authed_client

    response = client.post(
        reverse("accounts:complete_registration"),
        {"PhoneNumberForm-phone_number": "+27 11 555 1234"},
    )

    assert response.status_code == 302
    assert response.url == "/"
    user.refresh_from_db()
    # The fixture stores the value on the user via a signal-free save_field.
    from freedom_ls.accounts.tests._completion_view_fixtures import (
        STORED_PHONE_NUMBERS,
    )

    assert STORED_PHONE_NUMBERS[user.pk] == "+27 11 555 1234"


@pytest.mark.django_db
def test_posting_invalid_data_re_renders_with_errors(authed_client, site):
    SiteSignupPolicy.objects.create(
        site=site, additional_registration_forms=[PHONE_FORM_PATH]
    )
    client, user = authed_client

    response = client.post(
        reverse("accounts:complete_registration"),
        {"PhoneNumberForm-phone_number": ""},  # required field empty
    )

    assert response.status_code == 200
    from freedom_ls.accounts.tests._completion_view_fixtures import (
        STORED_PHONE_NUMBERS,
    )

    assert user.pk not in STORED_PHONE_NUMBERS


@pytest.mark.django_db
def test_next_param_honored_when_safe(authed_client, site, settings):
    settings.LOGIN_REDIRECT_URL = "/"
    SiteSignupPolicy.objects.create(
        site=site, additional_registration_forms=[PHONE_FORM_PATH]
    )
    client, _ = authed_client

    response = client.post(
        reverse("accounts:complete_registration") + "?next=/courses/",
        {
            "PhoneNumberForm-phone_number": "+27 11 555 1234",
            "next": "/courses/",
        },
    )

    assert response.status_code == 302
    assert response.url == "/courses/"


@pytest.mark.django_db
def test_unsafe_next_param_falls_back_to_login_redirect(authed_client, site, settings):
    settings.LOGIN_REDIRECT_URL = "/"
    SiteSignupPolicy.objects.create(
        site=site, additional_registration_forms=[PHONE_FORM_PATH]
    )
    client, _ = authed_client

    response = client.post(
        reverse("accounts:complete_registration"),
        {
            "PhoneNumberForm-phone_number": "+27 11 555 1234",
            "next": "https://evil.example.com/phish",
        },
    )

    assert response.status_code == 302
    assert response.url == "/"


@pytest.mark.django_db
def test_user_id_post_field_is_ignored(authed_client, site, settings):
    """The view always uses `request.user`; a `user_id` POST field is ignored."""
    settings.LOGIN_REDIRECT_URL = "/"
    SiteSignupPolicy.objects.create(
        site=site, additional_registration_forms=[PHONE_FORM_PATH]
    )
    client, user = authed_client
    other_user = UserFactory()

    response = client.post(
        reverse("accounts:complete_registration"),
        {
            "PhoneNumberForm-phone_number": "+27 11 555 1234",
            "user_id": str(other_user.pk),
        },
    )
    assert response.status_code == 302

    from freedom_ls.accounts.tests._completion_view_fixtures import (
        STORED_PHONE_NUMBERS,
    )

    # The stored phone is for the logged-in user, not the spoofed one.
    assert STORED_PHONE_NUMBERS[user.pk] == "+27 11 555 1234"
    assert other_user.pk not in STORED_PHONE_NUMBERS


@pytest.mark.django_db
def test_post_without_csrf_token_is_rejected(mock_site_context, site, settings):
    """Guards against an accidental CSRF-exemption regression."""
    settings.LOGIN_REDIRECT_URL = "/"
    SiteSignupPolicy.objects.create(
        site=site, additional_registration_forms=[PHONE_FORM_PATH]
    )
    user = UserFactory()
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)

    response = client.post(
        reverse("accounts:complete_registration"),
        {"PhoneNumberForm-phone_number": "+27 11 555 1234"},
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_get_with_next_renders_hidden_field(authed_client, site):
    SiteSignupPolicy.objects.create(
        site=site, additional_registration_forms=[PHONE_FORM_PATH]
    )
    client, _ = authed_client

    response = client.get(reverse("accounts:complete_registration") + "?next=/courses/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert 'name="next"' in body
    assert 'value="/courses/"' in body
