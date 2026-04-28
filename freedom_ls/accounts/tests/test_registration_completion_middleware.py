"""Tests for `RegistrationCompletionMiddleware`."""

from __future__ import annotations

import pytest

from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import SiteSignupPolicy

ALWAYS_INCOMPLETE_PATH = (
    "freedom_ls.accounts.tests._completion_view_fixtures.AlwaysIncompleteForm"
)
PHONE_FORM_PATH = "freedom_ls.accounts.tests._completion_view_fixtures.PhoneNumberForm"


@pytest.fixture
def login_url():
    return reverse("account_login")


@pytest.mark.django_db
def test_anonymous_request_passes_through(mock_site_context, login_url):
    client = Client()
    response = client.get(login_url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_superuser_passes_through_even_with_incomplete_forms(mock_site_context, site):
    SiteSignupPolicy.objects.create(
        site=site, additional_registration_forms=[ALWAYS_INCOMPLETE_PATH]
    )
    user = UserFactory(superuser=True)
    client = Client()
    client.force_login(user)

    # Hit a non-exempt path; profile redirects-with-200 because allauth
    # email may not be verified, but the middleware should not redirect to
    # complete_registration.
    response = client.get(reverse("accounts:account_profile"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_user_with_no_incomplete_forms_passes_through(mock_site_context, site):
    SiteSignupPolicy.objects.create(site=site, additional_registration_forms=[])
    user = UserFactory()
    client = Client()
    client.force_login(user)

    response = client.get(reverse("accounts:account_profile"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_user_with_incomplete_forms_redirected_to_completion(mock_site_context, site):
    SiteSignupPolicy.objects.create(
        site=site, additional_registration_forms=[ALWAYS_INCOMPLETE_PATH]
    )
    user = UserFactory()
    client = Client()
    client.force_login(user)

    response = client.get(reverse("accounts:account_profile"))
    assert response.status_code == 302
    assert response.url == reverse("accounts:complete_registration")


@pytest.mark.django_db
@pytest.mark.parametrize(
    "url_name",
    [
        "account_login",
        "account_logout",
        "account_signup",
        "account_email",
        "account_reset_password",
    ],
)
def test_allauth_exempt_url_names_pass_through(mock_site_context, site, url_name):
    SiteSignupPolicy.objects.create(
        site=site, additional_registration_forms=[ALWAYS_INCOMPLETE_PATH]
    )
    user = UserFactory()
    client = Client()
    client.force_login(user)

    url = reverse(url_name)
    response = client.get(url, follow=False)

    # Whatever each URL would normally do — what matters is that we are NOT
    # redirected to the completion view.
    assert response.status_code != 302 or response.url != reverse(
        "accounts:complete_registration"
    )


@pytest.mark.django_db
def test_legal_doc_url_is_exempt(mock_site_context, site):
    SiteSignupPolicy.objects.create(
        site=site, additional_registration_forms=[ALWAYS_INCOMPLETE_PATH]
    )
    user = UserFactory()
    client = Client()
    client.force_login(user)

    url = reverse("accounts:legal_doc", kwargs={"doc_type": "terms"})
    response = client.get(url)
    # The doc may or may not exist (404 if no docs), but the middleware
    # must NOT have intercepted with a redirect to complete_registration.
    if response.status_code == 302:
        assert response.url != reverse("accounts:complete_registration")


@pytest.mark.django_db
def test_completion_view_url_is_exempt(mock_site_context, site):
    SiteSignupPolicy.objects.create(
        site=site, additional_registration_forms=[ALWAYS_INCOMPLETE_PATH]
    )
    user = UserFactory()
    client = Client()
    client.force_login(user)

    response = client.get(reverse("accounts:complete_registration"))
    # Should reach the actual view (200) — not be redirected back into itself.
    assert response.status_code == 200


@pytest.mark.django_db
def test_health_path_exempt(mock_site_context, site):
    SiteSignupPolicy.objects.create(
        site=site, additional_registration_forms=[ALWAYS_INCOMPLETE_PATH]
    )
    user = UserFactory()
    client = Client()
    client.force_login(user)

    response = client.get("/health/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_substring_match_does_not_exempt(mock_site_context, site):
    """A path containing a substring of an exempt name is NOT exempt."""
    SiteSignupPolicy.objects.create(
        site=site, additional_registration_forms=[ALWAYS_INCOMPLETE_PATH]
    )
    user = UserFactory()
    client = Client()
    client.force_login(user)

    # `accounts:account_profile` is not in EXEMPT_URL_NAMES, so the user
    # should be redirected here.
    response = client.get(reverse("accounts:account_profile"))
    assert response.status_code == 302
    assert response.url == reverse("accounts:complete_registration")


@pytest.mark.django_db
def test_cache_short_circuits_second_request(mock_site_context, site):
    """After a `complete` evaluation, subsequent requests must not re-evaluate
    the user's forms (observable via the test fixture's call counter)."""
    from freedom_ls.accounts.tests import _completion_view_fixtures as fixtures

    SiteSignupPolicy.objects.create(
        site=site, additional_registration_forms=[PHONE_FORM_PATH]
    )
    user = UserFactory()
    fixtures.STORED_PHONE_NUMBERS[user.pk] = "+27 11 555 0001"
    fixtures.IS_COMPLETE_CALL_COUNT.clear()

    client = Client()
    client.force_login(user)

    # First request: middleware evaluates forms and marks complete.
    client.get(reverse("accounts:account_profile"))
    after_first = fixtures.IS_COMPLETE_CALL_COUNT.get("PhoneNumberForm", 0)

    # Second request: cached → no further evaluation.
    client.get(reverse("accounts:account_profile"))
    after_second = fixtures.IS_COMPLETE_CALL_COUNT.get("PhoneNumberForm", 0)

    assert after_first >= 1
    assert after_second == after_first  # no additional calls


@pytest.mark.django_db
def test_changing_dotted_paths_invalidates_cache(mock_site_context, site):
    """Switching the policy's `additional_registration_forms` re-evaluates."""
    from freedom_ls.accounts.tests import _completion_view_fixtures as fixtures

    fixtures.STORED_PHONE_NUMBERS.clear()
    fixtures.IS_COMPLETE_CALL_COUNT.clear()

    policy = SiteSignupPolicy.objects.create(
        site=site, additional_registration_forms=[]
    )
    user = UserFactory()
    client = Client()
    client.force_login(user)

    # First, no forms → marked complete.
    client.get(reverse("accounts:account_profile"))

    # Now switch the policy.
    policy.additional_registration_forms = [ALWAYS_INCOMPLETE_PATH]
    policy.save()

    response = client.get(reverse("accounts:account_profile"))
    assert response.status_code == 302
    assert response.url == reverse("accounts:complete_registration")


@pytest.mark.django_db
def test_completion_submit_clears_cache(mock_site_context, site, settings):
    """Submitting the completion view clears the cache so a subsequent
    policy change can take effect immediately on the same session."""
    from freedom_ls.accounts.tests import _completion_view_fixtures as fixtures

    settings.LOGIN_REDIRECT_URL = "/"
    fixtures.STORED_PHONE_NUMBERS.clear()
    fixtures.IS_COMPLETE_CALL_COUNT.clear()

    SiteSignupPolicy.objects.create(
        site=site, additional_registration_forms=[PHONE_FORM_PATH]
    )
    user = UserFactory()
    client = Client()
    client.force_login(user)

    # First request — incomplete, should redirect.
    response = client.get(reverse("accounts:account_profile"))
    assert response.url == reverse("accounts:complete_registration")

    # Submit the completion view.
    response = client.post(
        reverse("accounts:complete_registration"),
        {"PhoneNumberForm-phone_number": "+27 11 555 5555"},
    )
    assert response.status_code == 302

    # Subsequent request: now complete; should NOT redirect.
    response = client.get(reverse("accounts:account_profile"))
    assert response.status_code == 200
