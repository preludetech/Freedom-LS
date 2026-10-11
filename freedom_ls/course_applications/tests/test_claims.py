"""Tests for the claim token and the attach step."""

from __future__ import annotations

from datetime import timedelta

import pytest
import time_machine
from allauth.account import app_settings as allauth_account_settings

from django.utils import timezone

from freedom_ls.accounts.factories import SiteFactory, UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.course_applications"):
    pytest.skip("course_applications not installed", allow_module_level=True)

from freedom_ls.course_applications.claims import (
    ClaimLink,
    ClaimOutcome,
    attach_claimed_application,
    claim_token,
    read_claim_token,
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


def test_attaching_for_a_same_site_account_returns_that_account(mock_site_context, rf):
    user = UserFactory(email="taken@example.com")
    application = CourseApplicationFactory(anonymous=True)
    applicant = application.anonymous_applicant
    applicant.email = "TAKEN@example.com"
    applicant.save(update_fields=["email"])

    outcome = attach_claimed_application(rf.get("/"), application)

    assert outcome == ClaimOutcome(user, user_was_created=False)
