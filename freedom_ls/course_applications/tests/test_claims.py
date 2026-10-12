"""Tests for the claim token and the attach step."""

from __future__ import annotations

from datetime import timedelta

import pytest
import time_machine
from allauth.account import app_settings as allauth_account_settings
from allauth.account.models import EmailAddress

from django.contrib.sessions.backends.db import SessionStore
from django.utils import timezone

from freedom_ls.accounts.factories import EmailAddressFactory, SiteFactory, UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.course_applications"):
    pytest.skip("course_applications not installed", allow_module_level=True)

from freedom_ls.course_applications.claims import (
    ClaimLink,
    ClaimOutcome,
    ClaimOwner,
    attach_claimed_application,
    claim_sets_a_password,
    claim_token,
    read_claim_token,
    resolve_claim_owner,
)
from freedom_ls.course_applications.factories import CourseApplicationFactory

pytestmark = pytest.mark.django_db


def test_read_claim_token_round_trips_an_applicant(mock_site_context):
    application = CourseApplicationFactory(anonymous=True)
    applicant = application.anonymous_applicant

    link = read_claim_token(claim_token(applicant))

    assert link == ClaimLink(applicant, expired=False)


def test_tampered_claim_token_reads_as_none(mock_site_context):
    application = CourseApplicationFactory(anonymous=True)

    link = read_claim_token(claim_token(application.anonymous_applicant) + "x")

    assert link is None


def test_claim_token_past_the_confirmation_window_reads_as_expired(mock_site_context):
    application = CourseApplicationFactory(anonymous=True)
    applicant = application.anonymous_applicant
    token = claim_token(applicant)
    days = allauth_account_settings.EMAIL_CONFIRMATION_EXPIRE_DAYS

    with time_machine.travel(timezone.now() + timedelta(days=days, hours=1)):
        link = read_claim_token(token)

    assert link == ClaimLink(applicant, expired=True)


def test_attaching_an_already_claimed_applicant_returns_none(mock_site_context, rf):
    application = CourseApplicationFactory(anonymous=True)
    applicant = application.anonymous_applicant
    applicant.claimed_at = timezone.now()
    applicant.save(update_fields=["claimed_at"])

    outcome = attach_claimed_application(rf.get("/"), application)

    assert outcome is None


def test_attaching_an_already_claimed_applicant_creates_no_user(mock_site_context, rf):
    application = CourseApplicationFactory(anonymous=True)
    applicant = application.anonymous_applicant
    applicant.claimed_at = timezone.now()
    applicant.save(update_fields=["claimed_at"])
    users_before = User._base_manager.count()

    attach_claimed_application(rf.get("/"), application)

    assert User._base_manager.count() == users_before


def test_attaching_for_an_address_on_another_site_returns_none(mock_site_context, rf):
    UserFactory(site=SiteFactory(), email="taken@example.com")
    application = CourseApplicationFactory(anonymous=True)
    applicant = application.anonymous_applicant
    applicant.email = "taken@example.com"
    applicant.save(update_fields=["email"])

    outcome = attach_claimed_application(rf.get("/"), application)

    assert outcome is None


def test_attaching_for_an_address_on_another_site_creates_nothing(
    mock_site_context, rf
):
    UserFactory(site=SiteFactory(), email="taken@example.com")
    application = CourseApplicationFactory(anonymous=True)
    applicant = application.anonymous_applicant
    applicant.email = "taken@example.com"
    applicant.save(update_fields=["email"])
    users_before = User._base_manager.count()

    attach_claimed_application(rf.get("/"), application)

    assert User._base_manager.count() == users_before


def _anonymous_application_for(email: str):
    application = CourseApplicationFactory(anonymous=True)
    applicant = application.anonymous_applicant
    applicant.email = email
    applicant.save(update_fields=["email"])
    return application


def test_attaching_for_a_same_site_account_returns_that_account(mock_site_context, rf):
    user = UserFactory(email="taken@example.com")
    EmailAddressFactory(user=user)
    application = _anonymous_application_for("taken@example.com")

    outcome = attach_claimed_application(rf.get("/"), application)

    assert outcome == ClaimOutcome(user, must_set_password=False)


def test_resolving_an_address_held_as_a_verified_secondary_names_that_account(
    mock_site_context,
):
    user = UserFactory(email="primary@example.com")
    EmailAddressFactory(user=user)
    EmailAddressFactory(user=user, email="old@example.com", primary=False)
    application = _anonymous_application_for("old@example.com")

    owner = resolve_claim_owner(application.anonymous_applicant)

    assert owner == ClaimOwner(user, verified=True)


def test_attaching_for_a_verified_secondary_address_attaches_without_a_new_user(
    mock_site_context, rf
):
    user = UserFactory(email="primary@example.com")
    EmailAddressFactory(user=user)
    EmailAddressFactory(user=user, email="old@example.com", primary=False)
    application = _anonymous_application_for("old@example.com")

    outcome = attach_claimed_application(rf.get("/"), application)

    assert outcome == ClaimOutcome(user, must_set_password=False)


def test_an_unverified_secondary_address_makes_nobody_the_owner(mock_site_context):
    other = UserFactory(email="other@example.com")
    EmailAddressFactory(user=other)
    EmailAddressFactory(
        user=other, email="victim@example.com", verified=False, primary=False
    )
    application = _anonymous_application_for("victim@example.com")

    owner = resolve_claim_owner(application.anonymous_applicant)

    assert owner is None


def test_attaching_past_an_unverified_secondary_address_creates_a_new_user(
    mock_site_context, rf
):
    other = UserFactory(email="other@example.com")
    EmailAddressFactory(user=other)
    EmailAddressFactory(
        user=other, email="victim@example.com", verified=False, primary=False
    )
    application = _anonymous_application_for("victim@example.com")
    # A new account announces itself, which queues an analytics event in the session.
    request = rf.get("/")
    request.session = SessionStore()

    outcome = attach_claimed_application(request, application)

    assert outcome is not None
    assert (outcome.user != other, outcome.must_set_password) == (True, True)


def test_attaching_for_an_address_verified_on_another_site_returns_none(
    mock_site_context, rf
):
    user = UserFactory(site=SiteFactory(), email="primary@example.com")
    EmailAddressFactory(user=user, email="old@example.com", primary=False)
    application = _anonymous_application_for("old@example.com")

    outcome = attach_claimed_application(rf.get("/"), application)

    assert outcome is None


@pytest.fixture
def squatted_application(mock_site_context):
    """An address registered through signup and never verified."""
    squatter = UserFactory(email="victim@example.com", password="squatter-pass")
    EmailAddressFactory(user=squatter, verified=False)
    return _anonymous_application_for("victim@example.com"), squatter


def test_resolving_a_squatted_address_reports_an_unverified_signup(
    squatted_application,
):
    application, squatter = squatted_application

    owner = resolve_claim_owner(application.anonymous_applicant)

    assert owner == ClaimOwner(squatter, verified=False, unverified_signup=True)


def test_claiming_a_squatted_address_revokes_the_squatters_password(
    squatted_application, rf
):
    application, squatter = squatted_application

    attach_claimed_application(rf.get("/"), application)

    squatter.refresh_from_db()
    assert squatter.has_usable_password() is False


def test_claiming_a_squatted_address_verifies_it(squatted_application, rf):
    application, squatter = squatted_application

    attach_claimed_application(rf.get("/"), application)

    address = EmailAddress.objects.get(user=squatter, email="victim@example.com")
    assert address.verified is True


def test_claiming_a_squatted_address_asks_for_a_new_password(squatted_application, rf):
    application, squatter = squatted_application

    outcome = attach_claimed_application(rf.get("/"), application)

    assert outcome == ClaimOutcome(squatter, must_set_password=True)


def test_an_operator_created_account_keeps_its_password_when_claimed(
    mock_site_context, rf
):
    user = UserFactory(email="staffmade@example.com", password="their-own")
    application = _anonymous_application_for("staffmade@example.com")

    attach_claimed_application(rf.get("/"), application)

    user.refresh_from_db()
    assert user.check_password("their-own") is True


def test_an_operator_created_account_gains_a_verified_primary_address_when_claimed(
    mock_site_context, rf
):
    user = UserFactory(email="staffmade@example.com")
    application = _anonymous_application_for("staffmade@example.com")

    attach_claimed_application(rf.get("/"), application)

    address = EmailAddress.objects.get(user=user)
    assert (address.email, address.verified, address.primary) == (
        "staffmade@example.com",
        True,
        True,
    )


def test_a_claim_sets_a_password_only_when_nobody_has_proven_one(mock_site_context):
    user = UserFactory()

    assert (
        claim_sets_a_password(None),
        claim_sets_a_password(ClaimOwner(user, verified=True)),
        claim_sets_a_password(ClaimOwner(user, verified=False)),
        claim_sets_a_password(ClaimOwner(user, verified=False, unverified_signup=True)),
    ) == (True, False, False, True)
