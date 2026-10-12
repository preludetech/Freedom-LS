"""Tests for the claim token and the attach step."""

from __future__ import annotations

import threading
import time
from datetime import timedelta
from unittest.mock import patch

import pytest
import time_machine
from allauth.account import app_settings as allauth_account_settings
from allauth.account.models import EmailAddress

from django.contrib.sessions.backends.db import SessionStore
from django.db import IntegrityError, connection
from django.test import RequestFactory
from django.utils import timezone

from freedom_ls.accounts.factories import EmailAddressFactory, SiteFactory, UserFactory
from freedom_ls.accounts.models import LegalConsent, User
from freedom_ls.tests.app_guards import app_not_installed
from freedom_ls.tests.site_context import site_context

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
from freedom_ls.course_applications.models import AnonymousApplicant, CourseApplication
from freedom_ls.form_engine.factories import FormProgressFactory
from freedom_ls.form_engine.models import FormProgress

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

    assert outcome == ClaimOutcome(
        user, application=application, must_set_password=False
    )


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

    assert outcome == ClaimOutcome(
        user, application=application, must_set_password=False
    )


def test_an_unverified_secondary_address_makes_nobody_the_owner(mock_site_context):
    other = UserFactory(email="other@example.com")
    EmailAddressFactory(user=other)
    EmailAddressFactory(
        user=other, email="victim@example.com", verified=False, primary=False
    )
    application = _anonymous_application_for("victim@example.com")

    owner = resolve_claim_owner(application.anonymous_applicant)

    assert owner is None


def test_an_account_made_for_the_address_mid_claim_receives_the_application(
    mock_site_context, rf
):
    """The applicant lock does not cover the address. A signup, or the claim of
    a second application under the same address, can make the account between
    the owner lookup and the create; the application then goes to that account
    rather than failing on the unique address."""
    application = _anonymous_application_for("raced@example.com")
    racer: list[User] = []

    def _somebody_else_registers_first(applicant):
        racer.append(UserFactory(email=applicant.email))
        EmailAddressFactory(user=racer[0], email=applicant.email)
        raise IntegrityError("duplicate key value violates unique constraint")

    with patch(
        "freedom_ls.course_applications.claims._create_claimed_user",
        side_effect=_somebody_else_registers_first,
    ):
        outcome = attach_claimed_application(rf.get("/"), application)

    application.refresh_from_db()
    assert (application.user, outcome) == (
        racer[0],
        ClaimOutcome(racer[0], application=application, must_set_password=False),
    )
    assert User.objects.filter(email="raced@example.com").count() == 1


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


def test_a_claim_over_a_draft_on_the_account_replaces_the_draft(mock_site_context, rf):
    """The draft could only repeat a request already made, so it goes, and
    its sitting with it."""
    user = UserFactory(email="taken@example.com")
    EmailAddressFactory(user=user)
    application = _anonymous_application_for("taken@example.com")
    draft = CourseApplicationFactory(
        user=user,
        course=application.course,
        form_progress=FormProgressFactory(user=user),
    )
    draft_sitting_pk = draft.form_progress_id

    outcome = attach_claimed_application(rf.get("/"), application)

    application.refresh_from_db()
    assert outcome == ClaimOutcome(
        user, application=application, must_set_password=False
    )
    assert application.user == user
    assert not CourseApplication.objects.filter(pk=draft.pk).exists()
    assert not FormProgress.objects.filter(pk=draft_sitting_pk).exists()


def test_a_claim_over_a_submission_on_the_account_keeps_that_one(mock_site_context, rf):
    """Between two submissions the account's own stays; the claimed one is
    erased with its applicant and the claimant lands on the one that stays."""
    user = UserFactory(email="taken@example.com")
    EmailAddressFactory(user=user)
    application = _anonymous_application_for("taken@example.com")
    applicant_pk = application.anonymous_applicant_id
    held = CourseApplicationFactory(user=user, course=application.course)

    outcome = attach_claimed_application(rf.get("/"), application)

    assert outcome == ClaimOutcome(user, application=held, must_set_password=False)
    assert not CourseApplication.objects.filter(pk=application.pk).exists()
    assert not AnonymousApplicant.objects.filter(pk=applicant_pk).exists()
    assert list(CourseApplication.objects.filter(user=user)) == [held]


@pytest.mark.django_db(transaction=True)
def test_two_claims_for_one_address_and_course_at_once_leave_one_application(
    mock_site_context,
):
    """Two applications under one address to one course, both claim links
    confirmed at the same moment. Each transaction locks its own applicant,
    so the account's row is the lock both wait on: the second claim then
    finds what the first attached instead of failing on the unique
    (site, user, course).

    transaction=True, because each thread needs its own connection and the
    second has to see the first's commit."""
    site = mock_site_context
    user = UserFactory(email="twice@example.com")
    EmailAddressFactory(user=user)
    first_application = _anonymous_application_for("twice@example.com")
    second_application = CourseApplicationFactory(
        anonymous=True, course=first_application.course
    )
    second_application.anonymous_applicant.email = "twice@example.com"
    second_application.anonymous_applicant.save(update_fields=["email"])
    first_is_mid_attach = threading.Event()
    real_now = timezone.now
    failures: list[BaseException] = []

    def slow_first_now():
        # Called once per attach, after the application row is written and
        # before the transaction commits.
        if not first_is_mid_attach.is_set():
            first_is_mid_attach.set()
            time.sleep(0.5)
        return real_now()

    def claim(application) -> None:
        request = RequestFactory().get("/")
        try:
            with site_context(site):
                attach_claimed_application(request, application)
        except BaseException as exc:
            failures.append(exc)
        finally:
            connection.close()

    with patch("freedom_ls.course_applications.claims.timezone.now", slow_first_now):
        first = threading.Thread(target=claim, args=(first_application,))
        first.start()
        assert first_is_mid_attach.wait(timeout=5)
        second = threading.Thread(target=claim, args=(second_application,))
        second.start()
        first.join(timeout=10)
        second.join(timeout=10)

    assert failures == []
    assert CourseApplication.objects.filter(user=user).count() == 1


@pytest.fixture
def squatted_application(mock_site_context):
    """An address registered through signup and never verified."""
    squatter = UserFactory(email="victim@example.com", password="squatter-pass")
    EmailAddressFactory(user=squatter, verified=False)
    return _anonymous_application_for("victim@example.com"), squatter


def test_resolving_a_squatted_address_reports_an_unverified_owner(
    squatted_application,
):
    application, squatter = squatted_application

    owner = resolve_claim_owner(application.anonymous_applicant)

    assert owner == ClaimOwner(squatter, verified=False)


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

    assert outcome == ClaimOutcome(
        squatter, application=application, must_set_password=True
    )


def test_claiming_a_squatted_address_writes_the_claimants_consent(
    squatted_application, rf
):
    """The squatter's password goes, so their consent is not the claimant's."""
    application, squatter = squatted_application
    applicant = application.anonymous_applicant
    applicant.terms_version = "1.2"
    applicant.terms_git_hash = "a" * 40
    applicant.privacy_version = "2.0"
    applicant.privacy_git_hash = "b" * 40
    applicant.consent_ip_address = "203.0.113.9"
    applicant.save()

    attach_claimed_application(rf.get("/"), application)

    consents = LegalConsent.objects.filter(
        user=squatter, consent_method="application_details_step"
    )
    assert sorted(consents.values_list("document_type", "document_version")) == [
        ("privacy", "2.0"),
        ("terms", "1.2"),
    ]


def test_an_operator_created_account_has_its_password_revoked_when_claimed(
    mock_site_context, rf
):
    """Whoever set that password never proved they owned the mailbox either."""
    user = UserFactory(email="staffmade@example.com", password="their-own")
    application = _anonymous_application_for("staffmade@example.com")

    outcome = attach_claimed_application(rf.get("/"), application)

    user.refresh_from_db()
    assert (user.has_usable_password(), outcome) == (
        False,
        ClaimOutcome(user, application=application, must_set_password=True),
    )


@pytest.fixture
def login_synced_application(mock_site_context):
    """An operator-made account after one login attempt.

    allauth writes an unverified, non-primary row for the login address the
    first time such an account tries to sign in.
    """
    user = UserFactory(email="staffmade@example.com", password="their-own")
    EmailAddressFactory(user=user, verified=False, primary=False)
    return _anonymous_application_for("staffmade@example.com"), user


def test_claiming_a_login_synced_address_revokes_the_password(
    login_synced_application, rf
):
    application, user = login_synced_application

    attach_claimed_application(rf.get("/"), application)

    user.refresh_from_db()
    assert user.has_usable_password() is False


def test_claiming_a_login_synced_address_verifies_the_one_row(
    login_synced_application, rf
):
    application, user = login_synced_application

    attach_claimed_application(rf.get("/"), application)

    addresses = EmailAddress.objects.filter(user=user)
    assert [(a.email, a.verified, a.primary) for a in addresses] == [
        ("staffmade@example.com", True, True)
    ]


def test_a_verified_owner_without_a_usable_password_sets_one_on_claim(
    mock_site_context, rf
):
    """An earlier claim that never reached the set-password page leaves the
    account with no password anyone knows."""
    user = UserFactory(email="taken@example.com")
    user.set_unusable_password()
    user.save(update_fields=["password"])
    EmailAddressFactory(user=user)
    application = _anonymous_application_for("taken@example.com")

    outcome = attach_claimed_application(rf.get("/"), application)

    assert outcome == ClaimOutcome(
        user, application=application, must_set_password=True
    )


def test_resolving_a_verified_address_stored_in_mixed_case_finds_it(
    mock_site_context,
):
    user = UserFactory(email="Ada.Lovelace@example.com")
    EmailAddressFactory(user=user, email="Ada.Lovelace@example.com")
    application = _anonymous_application_for("ada.lovelace@example.com")

    owner = resolve_claim_owner(application.anonymous_applicant)

    assert owner == ClaimOwner(user, verified=True)


def test_claiming_a_mixed_case_verified_address_adds_no_second_row(
    mock_site_context, rf
):
    user = UserFactory(email="Ada.Lovelace@example.com")
    EmailAddressFactory(user=user, email="Ada.Lovelace@example.com")
    application = _anonymous_application_for("ada.lovelace@example.com")

    attach_claimed_application(rf.get("/"), application)

    assert EmailAddress.objects.filter(user=user).count() == 1


def test_claiming_a_mixed_case_unverified_address_verifies_that_row(
    mock_site_context, rf
):
    user = UserFactory(email="Ada.Lovelace@example.com")
    EmailAddressFactory(user=user, email="Ada.Lovelace@example.com", verified=False)
    application = _anonymous_application_for("ada.lovelace@example.com")

    attach_claimed_application(rf.get("/"), application)

    addresses = EmailAddress.objects.filter(user=user)
    assert [(a.email, a.verified) for a in addresses] == [
        ("Ada.Lovelace@example.com", True)
    ]


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
    passwordless = UserFactory()
    passwordless.set_unusable_password()

    assert (
        claim_sets_a_password(None),
        claim_sets_a_password(ClaimOwner(user, verified=True)),
        claim_sets_a_password(ClaimOwner(user, verified=False)),
        claim_sets_a_password(ClaimOwner(passwordless, verified=True)),
    ) == (True, False, True, True)
