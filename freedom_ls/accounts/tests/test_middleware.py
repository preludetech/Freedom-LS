"""Tests for `RegistrationCompletionMiddleware`."""

from __future__ import annotations

from datetime import timedelta

import pytest
import time_machine

from django.db.models.signals import post_save
from django.http import HttpRequest, HttpResponse
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import SiteSignupPolicyFactory, UserFactory
from freedom_ls.accounts.middleware import LastActiveMiddleware
from freedom_ls.accounts.models import User
from freedom_ls.accounts.tests import _completion_view_fixtures as fixtures
from freedom_ls.api.scopes import ApiScope
from freedom_ls.api.tests.helpers import bearer_auth_for

ALWAYS_INCOMPLETE_PATH = (
    "freedom_ls.accounts.tests._completion_view_fixtures.AlwaysIncompleteForm"
)
PERSONAL_DETAILS_URL = "/accounts/profile/personal-details"
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
    response = client.get(PERSONAL_DETAILS_URL)
    assert response.status_code == 200


@pytest.mark.django_db
def test_user_with_no_incomplete_forms_passes_through(mock_site_context, site):
    SiteSignupPolicyFactory(site=site, additional_registration_forms=[])
    user = UserFactory()
    client = Client()
    client.force_login(user)

    response = client.get(PERSONAL_DETAILS_URL)
    assert response.status_code == 200


@pytest.mark.django_db
def test_user_with_incomplete_forms_redirected_to_completion(mock_site_context, site):
    SiteSignupPolicyFactory(
        site=site, additional_registration_forms=[ALWAYS_INCOMPLETE_PATH]
    )
    user = UserFactory()
    client = Client()
    client.force_login(user)

    profile_url = PERSONAL_DETAILS_URL
    response = client.get(profile_url)
    assert response.status_code == 302
    completion_url = reverse("accounts:complete_registration")
    assert response.url.startswith(completion_url)


@pytest.mark.django_db
def test_get_by_incomplete_user_carries_own_path_as_next(mock_site_context, site):
    """A GET that gets bounced to completion carries its own path as `next`,
    so the visitor lands back where they were once the form is done."""
    SiteSignupPolicyFactory(
        site=site, additional_registration_forms=[ALWAYS_INCOMPLETE_PATH]
    )
    user = UserFactory()
    client = Client()
    client.force_login(user)

    profile_url = PERSONAL_DETAILS_URL
    response = client.get(profile_url)

    completion_url = reverse("accounts:complete_registration")
    assert response.status_code == 302
    assert response.url == f"{completion_url}?next={profile_url}"


@pytest.mark.django_db
def test_post_by_incomplete_user_redirects_without_next(mock_site_context, site):
    """A POST cannot be safely replayed as `next`, so the redirect carries
    none — replaying it would GET a URL that only accepts POST."""
    SiteSignupPolicyFactory(
        site=site, additional_registration_forms=[ALWAYS_INCOMPLETE_PATH]
    )
    user = UserFactory()
    client = Client()
    client.force_login(user)

    response = client.post(PERSONAL_DETAILS_URL)

    completion_url = reverse("accounts:complete_registration")
    assert response.status_code == 302
    assert response.url == completion_url


@pytest.mark.django_db
def test_htmx_incomplete_user_gets_204_with_hx_redirect(mock_site_context, site):
    """An htmx request must not have a login page swapped into a fragment,
    so it gets 204 + HX-Redirect instead of a 302 htmx would follow itself.

    It carries no `next`: an htmx path is a partial, which renders as a bare
    fragment if the browser navigates to it full-page after the form."""
    SiteSignupPolicyFactory(
        site=site, additional_registration_forms=[ALWAYS_INCOMPLETE_PATH]
    )
    user = UserFactory()
    client = Client()
    client.force_login(user)

    profile_url = PERSONAL_DETAILS_URL
    response = client.get(profile_url, HTTP_HX_REQUEST="true")

    completion_url = reverse("accounts:complete_registration")
    assert response.status_code == 204
    assert response["HX-Redirect"] == completion_url


@pytest.mark.django_db
def test_settings_default_drives_forms_when_no_policy(mock_site_context, settings):
    """settings.ADDITIONAL_REGISTRATION_FORMS is used when no policy exists."""
    settings.ADDITIONAL_REGISTRATION_FORMS = [ALWAYS_INCOMPLETE_PATH]

    user = UserFactory()
    client = Client()
    client.force_login(user)

    profile_url = PERSONAL_DETAILS_URL
    response = client.get(profile_url)
    assert response.status_code == 302
    completion_url = reverse("accounts:complete_registration")
    assert response.url.startswith(completion_url)


@pytest.mark.django_db
def test_policy_overrides_settings_additional_registration_forms(
    mock_site_context, site, settings
):
    """A per-site policy with an empty list overrides a non-empty settings default."""
    settings.ADDITIONAL_REGISTRATION_FORMS = [ALWAYS_INCOMPLETE_PATH]
    SiteSignupPolicyFactory(site=site, additional_registration_forms=[])

    user = UserFactory()
    client = Client()
    client.force_login(user)

    response = client.get(PERSONAL_DETAILS_URL)
    assert response.status_code == 200


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

    response = client.get("/health/liveness/")
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
    # should be redirected to complete_registration.
    profile_url = PERSONAL_DETAILS_URL
    response = client.get(profile_url)
    assert response.status_code == 302
    completion_url = reverse("accounts:complete_registration")
    assert response.url.startswith(completion_url)


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
    first = client.get(PERSONAL_DETAILS_URL)
    assert first.status_code == 200

    # Mutate underlying state: an un-cached re-evaluation would now report
    # the user as incomplete and redirect.
    fixtures.STORED_PHONE_NUMBERS.pop(user.pk, None)

    # Second request: cache returns the stale "complete" verdict.
    second = client.get(PERSONAL_DETAILS_URL)
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
    client.get(PERSONAL_DETAILS_URL)

    # Now switch the policy.
    policy.additional_registration_forms = [ALWAYS_INCOMPLETE_PATH]
    policy.save()

    profile_url = PERSONAL_DETAILS_URL
    response = client.get(profile_url)
    assert response.status_code == 302
    completion_url = reverse("accounts:complete_registration")
    assert response.url.startswith(completion_url)


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
    client.get(PERSONAL_DETAILS_URL)

    # Act: submit the completion form.
    client.post(
        reverse("accounts:complete_registration"),
        {"PhoneNumberForm-phone_number": "+27 11 555 5555"},
    )

    # Assert: cache cleared — next request reaches the profile page.
    response = client.get(PERSONAL_DETAILS_URL)
    assert response.status_code == 200


def _run_last_active(user: User | None) -> HttpRequest:
    """Pass one request for `user` (anonymous when None) through the middleware."""
    from django.contrib.auth.models import AnonymousUser

    request = HttpRequest()
    request.user = user if user is not None else AnonymousUser()
    LastActiveMiddleware(lambda _request: HttpResponse())(request)
    return request


def _stored_last_active(user: User):
    return User._base_manager.values_list("last_active", flat=True).get(pk=user.pk)


@pytest.mark.django_db
def test_last_active_null_value_is_written(mock_site_context):
    user = UserFactory(last_active=None)

    _run_last_active(user)

    assert _stored_last_active(user) is not None
    assert user.last_active == _stored_last_active(user)


@pytest.mark.django_db
def test_last_active_stale_value_is_moved(mock_site_context):
    user = UserFactory(last_active=timezone.now() - timedelta(hours=1))
    stale = _stored_last_active(user)

    with time_machine.travel(timezone.now() + timedelta(seconds=10)):
        _run_last_active(user)

    assert _stored_last_active(user) > stale + timedelta(minutes=59)


@pytest.mark.django_db
def test_last_active_fresh_value_costs_no_query(
    mock_site_context, django_assert_num_queries
):
    user = UserFactory(last_active=timezone.now())

    with django_assert_num_queries(0):
        _run_last_active(user)


@pytest.mark.django_db
def test_last_active_anonymous_request_writes_nothing(
    mock_site_context, django_assert_num_queries
):
    with django_assert_num_queries(0):
        _run_last_active(None)


@pytest.mark.django_db
def test_last_active_api_key_request_leaves_it_null(mock_site_context):
    user = UserFactory(last_active=None)

    response = Client().get(
        reverse("api:user_list"), headers=bearer_auth_for(ApiScope.USERS)
    )

    assert response.status_code == 200
    assert _stored_last_active(user) is None


@pytest.mark.django_db
def test_last_active_write_leaves_updated_at_and_last_login_alone(mock_site_context):
    user = UserFactory(last_active=None)
    before = User._base_manager.values_list("updated_at", "last_login").get(pk=user.pk)

    _run_last_active(user)

    after = User._base_manager.values_list("updated_at", "last_login").get(pk=user.pk)
    assert after == before


@pytest.mark.django_db
def test_last_active_write_sends_no_post_save(mock_site_context):
    user = UserFactory(last_active=None)
    received: list[object] = []

    def receiver(sender: object, **kwargs: object) -> None:
        received.append(sender)

    post_save.connect(receiver, sender=User)
    try:
        _run_last_active(user)
    finally:
        post_save.disconnect(receiver, sender=User)

    assert received == []


@pytest.mark.django_db
def test_last_active_write_seconds_override_is_honoured(mock_site_context):
    user = UserFactory(last_active=timezone.now() - timedelta(seconds=30))
    before = _stored_last_active(user)

    with override_settings(LAST_ACTIVE_WRITE_SECONDS=10):
        _run_last_active(user)

    assert _stored_last_active(user) > before


@pytest.mark.django_db
def test_last_active_is_written_through_the_middleware_stack(mock_site_context):
    user = UserFactory(last_active=None)
    client = Client()
    client.force_login(user)

    client.get(PERSONAL_DETAILS_URL)

    last_active = _stored_last_active(user)
    assert last_active is not None
    assert timezone.now() - last_active < timedelta(seconds=300)
