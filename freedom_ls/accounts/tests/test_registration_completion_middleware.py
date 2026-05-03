"""Tests for `RegistrationCompletionMiddleware`."""

from __future__ import annotations

import pytest

from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import SiteSignupPolicyFactory, UserFactory
from freedom_ls.accounts.tests import _completion_view_fixtures as fixtures

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
    SiteSignupPolicyFactory(
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
    SiteSignupPolicyFactory(site=site, additional_registration_forms=[])
    user = UserFactory()
    client = Client()
    client.force_login(user)

    response = client.get(reverse("accounts:account_profile"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_user_with_incomplete_forms_redirected_to_completion(mock_site_context, site):
    SiteSignupPolicyFactory(
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
    SiteSignupPolicyFactory(
        site=site, additional_registration_forms=[ALWAYS_INCOMPLETE_PATH]
    )
    user = UserFactory()
    client = Client()
    client.force_login(user)

    url = reverse(url_name)
    response = client.get(url, follow=False)

    # Whatever each URL would normally do — what matters is that we are NOT
    # redirected to the completion view.
    completion_url = reverse("accounts:complete_registration")
    redirected_to_completion = (
        response.status_code == 302 and response.url == completion_url
    )
    assert redirected_to_completion is False


@pytest.mark.django_db
def test_legal_doc_url_is_exempt(mock_site_context, site):
    SiteSignupPolicyFactory(
        site=site, additional_registration_forms=[ALWAYS_INCOMPLETE_PATH]
    )
    user = UserFactory()
    client = Client()
    client.force_login(user)

    url = reverse("accounts:legal_doc", kwargs={"doc_type": "terms"})
    response = client.get(url)

    # The doc may or may not exist (404 if no docs), but the middleware
    # must NOT have intercepted with a redirect to complete_registration.
    completion_url = reverse("accounts:complete_registration")
    redirected_to_completion = (
        response.status_code == 302 and response.url == completion_url
    )
    assert redirected_to_completion is False


@pytest.mark.django_db
def test_completion_view_url_is_exempt(mock_site_context, site):
    SiteSignupPolicyFactory(
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
    SiteSignupPolicyFactory(
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
    SiteSignupPolicyFactory(
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
    """Once a user has been marked complete, the cached verdict survives
    even when the underlying form state is invalidated — proving that the
    middleware did not re-evaluate the form on the second request."""
    SiteSignupPolicyFactory(site=site, additional_registration_forms=[PHONE_FORM_PATH])
    user = UserFactory()
    fixtures.STORED_PHONE_NUMBERS[user.pk] = "+27 11 555 0001"

    client = Client()
    client.force_login(user)

    # First request: form is complete → user passes through to profile.
    first = client.get(reverse("accounts:account_profile"))
    assert first.status_code == 200

    # Mutate underlying state: an un-cached re-evaluation would now report
    # the user as incomplete and redirect.
    fixtures.STORED_PHONE_NUMBERS.pop(user.pk, None)

    # Second request: cache returns the stale "complete" verdict.
    second = client.get(reverse("accounts:account_profile"))
    assert second.status_code == 200


@pytest.mark.django_db
def test_changing_dotted_paths_invalidates_cache(mock_site_context, site):
    """Switching the policy's `additional_registration_forms` re-evaluates."""
    fixtures.STORED_PHONE_NUMBERS.clear()
    fixtures.IS_COMPLETE_CALL_COUNT.clear()

    policy = SiteSignupPolicyFactory(site=site, additional_registration_forms=[])
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
    """Submitting the completion view clears the cached `incomplete` verdict.

    Without this, a user submitting the form would still be bounced back
    to the completion view on their next page-load until the cache aged
    out. The test arranges a poisoned cache (one GET while incomplete),
    submits the form, then re-checks that the next page is not redirected.
    """
    settings.LOGIN_REDIRECT_URL = "/"
    fixtures.STORED_PHONE_NUMBERS.clear()

    SiteSignupPolicyFactory(site=site, additional_registration_forms=[PHONE_FORM_PATH])
    user = UserFactory()
    client = Client()
    client.force_login(user)

    # Arrange: prime the cache with an "incomplete" verdict.
    client.get(reverse("accounts:account_profile"))

    # Act: submit the completion form.
    client.post(
        reverse("accounts:complete_registration"),
        {"PhoneNumberForm-phone_number": "+27 11 555 5555"},
    )

    # Assert: cache cleared — next request reaches the profile page.
    response = client.get(reverse("accounts:account_profile"))
    assert response.status_code == 200
