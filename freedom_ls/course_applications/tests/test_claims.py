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
from django.core import signing
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
    CLAIM_TOKEN_SALT,
    AttachResult,
    ClaimLink,
    ClaimOutcome,
    ClaimOwner,
    attach_claimed_application,
    attach_to_user,
    claim_sets_a_password,
    claim_token,
    read_claim_token,
    resolve_claim_owner,
    update_applicant_email,
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


def test_bare_pk_claim_token_reads_as_the_applicant_at_version_zero(mock_site_context):
    application = CourseApplicationFactory(anonymous=True)
    applicant = application.anonymous_applicant
    token = signing.dumps(str(applicant.pk), salt=CLAIM_TOKEN_SALT)

    link = read_claim_token(token)

    assert link == ClaimLink(applicant, expired=False)


def test_bare_pk_claim_token_reads_as_none_once_the_version_has_moved(
    mock_site_context,
):
    application = CourseApplicationFactory(anonymous=True)
    applicant = application.anonymous_applicant
    token = signing.dumps(str(applicant.pk), salt=CLAIM_TOKEN_SALT)
    update_applicant_email(applicant, "other@example.com")

    link = read_claim_token(token)

    assert link is None


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(
            {"a": "00000000-0000-0000-0000-000000000000"}, id="dict-without-v"
        ),
        pytest.param({"a": "not-a-uuid", "v": 0}, id="non-uuid-pk"),
        pytest.param(["a", 0], id="list"),
    ],
)
def test_claim_token_of_a_validly_signed_wrong_shape_reads_as_none(
    mock_site_context, payload
):
    token = signing.dumps(payload, salt=CLAIM_TOKEN_SALT)

    link = read_claim_token(token)

    assert link is None


def test_claim_token_minted_before_an_address_change_reads_as_none(mock_site_context):
    application = CourseApplicationFactory(anonymous=True)
    applicant = application.anonymous_applicant
    token = claim_token(applicant)
    update_applicant_email(applicant, "other@example.com")

    link = read_claim_token(token)

    assert link is None


def test_expired_claim_token_minted_before_an_address_change_reads_as_none(
    mock_site_context,
):
    application = CourseApplicationFactory(anonymous=True)
    applicant = application.anonymous_applicant
    token = claim_token(applicant)
    update_applicant_email(applicant, "other@example.com")
    days = allauth_account_settings.EMAIL_CONFIRMATION_EXPIRE_DAYS

    with time_machine.travel(timezone.now() + timedelta(days=days, hours=1)):
        link = read_claim_token(token)

    assert link is None


def test_changing_the_address_away_and_back_leaves_the_first_link_invalid(
    mock_site_context,
):
    application = CourseApplicationFactory(anonymous=True)
    applicant = application.anonymous_applicant
    original = applicant.email
    token = claim_token(applicant)
    update_applicant_email(applicant, "other@example.com")
    update_applicant_email(applicant, original)

    link = read_claim_token(token)

    assert link is None


@pytest.mark.parametrize("spelling", ["same", "upper", "padded"])
def test_update_applicant_email_with_the_stored_address_returns_false(
    mock_site_context, spelling
):
    application = CourseApplicationFactory(anonymous=True)
    applicant = application.anonymous_applicant
    posted = {
        "same": applicant.email,
        "upper": applicant.email.upper(),
        "padded": f"  {applicant.email} ",
    }[spelling]

    changed = update_applicant_email(applicant, posted)

    assert changed is False


def test_update_applicant_email_with_the_stored_address_keeps_version_and_stamp(
    mock_site_context,
):
    sent_at = timezone.now()
    application = CourseApplicationFactory(anonymous=True)
    applicant = application.anonymous_applicant
    applicant.claim_email_sent_at = sent_at
    applicant.save(update_fields=["claim_email_sent_at"])

    update_applicant_email(applicant, f"  {applicant.email.upper()} ")

    applicant.refresh_from_db()
    assert (applicant.claim_link_version, applicant.claim_email_sent_at) == (0, sent_at)


def test_update_applicant_email_with_a_new_address_returns_true(mock_site_context):
    applicant = CourseApplicationFactory(anonymous=True).anonymous_applicant

    changed = update_applicant_email(applicant, "New@Example.com")

    assert changed is True


def test_update_applicant_email_with_a_new_address_stores_it_lowercased(
    mock_site_context,
):
    applicant = CourseApplicationFactory(anonymous=True).anonymous_applicant

    update_applicant_email(applicant, " New@Example.com ")

    applicant.refresh_from_db()
    assert applicant.email == "new@example.com"


def test_update_applicant_email_with_a_new_address_bumps_the_version(mock_site_context):
    applicant = CourseApplicationFactory(anonymous=True).anonymous_applicant

    update_applicant_email(applicant, "new@example.com")

    applicant.refresh_from_db()
    assert applicant.claim_link_version == 1


def test_update_applicant_email_bumps_the_stored_version_not_a_stale_copy(
    mock_site_context,
):
    applicant = CourseApplicationFactory(anonymous=True).anonymous_applicant
    # Another request changed the address twice since this copy was read.
    AnonymousApplicant.objects.filter(pk=applicant.pk).update(claim_link_version=2)

    update_applicant_email(applicant, "new@example.com")

    stored = AnonymousApplicant.objects.get(pk=applicant.pk)
    assert (stored.claim_link_version, applicant.claim_link_version) == (3, 3)


def test_update_applicant_email_compares_against_the_stored_address(
    mock_site_context,
):
    applicant = CourseApplicationFactory(anonymous=True).anonymous_applicant
    AnonymousApplicant.objects.filter(pk=applicant.pk).update(
        email="new@example.com", claim_link_version=1
    )

    changed = update_applicant_email(applicant, "new@example.com")

    assert changed is False
    assert AnonymousApplicant.objects.get(pk=applicant.pk).claim_link_version == 1


def test_update_applicant_email_with_a_new_address_clears_the_sent_stamp(
    mock_site_context,
):
    applicant = CourseApplicationFactory(anonymous=True).anonymous_applicant
    applicant.claim_email_sent_at = timezone.now()
    applicant.save(update_fields=["claim_email_sent_at"])

    update_applicant_email(applicant, "new@example.com")

    applicant.refresh_from_db()
    assert applicant.claim_email_sent_at is None


def test_attaching_with_a_link_to_an_address_since_changed_returns_none(
    mock_site_context, rf
):
    application = CourseApplicationFactory(anonymous=True)
    # The address changed after the link was read, before the claim locked it.
    update_applicant_email(application.anonymous_applicant, "other@example.com")

    outcome = attach_claimed_application(rf.get("/"), application, link_version=0)

    assert outcome is None


def test_attaching_with_a_link_to_an_address_since_changed_creates_no_user(
    mock_site_context, rf
):
    application = CourseApplicationFactory(anonymous=True)
    update_applicant_email(application.anonymous_applicant, "other@example.com")
    users_before = User._base_manager.count()

    attach_claimed_application(rf.get("/"), application, link_version=0)

    assert User._base_manager.count() == users_before


def test_attaching_an_already_claimed_applicant_returns_none(mock_site_context, rf):
    application = CourseApplicationFactory(anonymous=True)
    applicant = application.anonymous_applicant
    applicant.claimed_at = timezone.now()
    applicant.save(update_fields=["claimed_at"])

    outcome = attach_claimed_application(rf.get("/"), application, link_version=0)

    assert outcome is None


def test_attaching_an_already_claimed_applicant_creates_no_user(mock_site_context, rf):
    application = CourseApplicationFactory(anonymous=True)
    applicant = application.anonymous_applicant
    applicant.claimed_at = timezone.now()
    applicant.save(update_fields=["claimed_at"])
    users_before = User._base_manager.count()

    attach_claimed_application(rf.get("/"), application, link_version=0)

    assert User._base_manager.count() == users_before


def test_attaching_for_an_address_on_another_site_returns_none(mock_site_context, rf):
    UserFactory(site=SiteFactory(), email="taken@example.com")
    application = CourseApplicationFactory(anonymous=True)
    applicant = application.anonymous_applicant
    applicant.email = "taken@example.com"
    applicant.save(update_fields=["email"])

    outcome = attach_claimed_application(rf.get("/"), application, link_version=0)

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

    attach_claimed_application(rf.get("/"), application, link_version=0)

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

    outcome = attach_claimed_application(rf.get("/"), application, link_version=0)

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

    outcome = attach_claimed_application(rf.get("/"), application, link_version=0)

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
        outcome = attach_claimed_application(rf.get("/"), application, link_version=0)

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

    outcome = attach_claimed_application(request, application, link_version=0)

    assert outcome is not None
    assert (outcome.user != other, outcome.must_set_password) == (True, True)


def test_attaching_for_an_address_verified_on_another_site_returns_none(
    mock_site_context, rf
):
    user = UserFactory(site=SiteFactory(), email="primary@example.com")
    EmailAddressFactory(user=user, email="old@example.com", primary=False)
    application = _anonymous_application_for("old@example.com")

    outcome = attach_claimed_application(rf.get("/"), application, link_version=0)

    assert outcome is None


def test_a_claim_over_a_draft_on_the_account_replaces_the_draft(mock_site_context, rf):
    """The incoming application is a request the account has not yet made, so
    it wins; the unfinished draft goes, and its sitting with it."""
    user = UserFactory(email="taken@example.com")
    EmailAddressFactory(user=user)
    application = _anonymous_application_for("taken@example.com")
    draft = CourseApplicationFactory(
        user=user,
        course=application.course,
        form_progress=FormProgressFactory(user=user),
    )
    draft_sitting_pk = draft.form_progress_id

    outcome = attach_claimed_application(rf.get("/"), application, link_version=0)

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

    outcome = attach_claimed_application(rf.get("/"), application, link_version=0)

    assert outcome == ClaimOutcome(user, application=held, must_set_password=False)
    assert not CourseApplication.objects.filter(pk=application.pk).exists()
    assert not AnonymousApplicant.objects.filter(pk=applicant_pk).exists()
    assert list(CourseApplication.objects.filter(user=user)) == [held]


def _anonymous_draft_for(email: str, course=None):
    application = CourseApplicationFactory(
        anonymous=True,
        **({"course": course} if course is not None else {}),
        form_progress=FormProgressFactory(user=None, completed_time=None),
    )
    applicant = application.anonymous_applicant
    applicant.email = email
    applicant.save(update_fields=["email"])
    return application


@pytest.fixture
def account_with_user(mock_site_context):
    user = UserFactory(email="taken@example.com")
    EmailAddressFactory(user=user)
    return user


def _held_draft(user, course):
    return CourseApplicationFactory(
        user=user,
        course=course,
        form_progress=FormProgressFactory(user=user, completed_time=None),
    )


def test_a_draft_claim_over_a_submission_on_the_account_keeps_the_submission(
    account_with_user, rf
):
    incoming = _anonymous_draft_for("taken@example.com")
    held = CourseApplicationFactory(user=account_with_user, course=incoming.course)

    outcome = attach_claimed_application(rf.get("/"), incoming, link_version=0)

    assert outcome == ClaimOutcome(
        account_with_user, application=held, must_set_password=False
    )


def test_a_draft_claim_over_a_submission_on_the_account_erases_the_incoming_draft(
    account_with_user, rf
):
    incoming = _anonymous_draft_for("taken@example.com")
    applicant_pk = incoming.anonymous_applicant_id
    sitting_pk = incoming.form_progress_id
    CourseApplicationFactory(user=account_with_user, course=incoming.course)

    attach_claimed_application(rf.get("/"), incoming, link_version=0)

    assert (
        CourseApplication.objects.filter(pk=incoming.pk).exists(),
        AnonymousApplicant.objects.filter(pk=applicant_pk).exists(),
        FormProgress.objects.filter(pk=sitting_pk).exists(),
    ) == (False, False, False)


def test_a_draft_claim_over_a_draft_on_the_account_attaches_the_incoming_draft(
    account_with_user, rf
):
    incoming = _anonymous_draft_for("taken@example.com")
    _held_draft(account_with_user, incoming.course)

    outcome = attach_claimed_application(rf.get("/"), incoming, link_version=0)

    assert outcome == ClaimOutcome(
        account_with_user, application=incoming, must_set_password=False
    )


def test_a_draft_claim_over_a_draft_on_the_account_deletes_the_held_draft(
    account_with_user, rf
):
    incoming = _anonymous_draft_for("taken@example.com")
    held = _held_draft(account_with_user, incoming.course)
    held_sitting_pk = held.form_progress_id

    attach_claimed_application(rf.get("/"), incoming, link_version=0)

    assert (
        CourseApplication.objects.filter(pk=held.pk).exists(),
        FormProgress.objects.filter(pk=held_sitting_pk).exists(),
    ) == (False, False)


def test_a_draft_claim_over_a_draft_on_the_account_gives_the_incoming_sitting_the_user(
    account_with_user, rf
):
    incoming = _anonymous_draft_for("taken@example.com")
    _held_draft(account_with_user, incoming.course)

    attach_claimed_application(rf.get("/"), incoming, link_version=0)

    incoming.form_progress.refresh_from_db()
    assert incoming.form_progress.user == account_with_user


def test_attaching_over_a_held_draft_reports_the_draft_as_discarded(
    account_with_user,
):
    incoming = _anonymous_draft_for("taken@example.com")
    _held_draft(account_with_user, incoming.course)

    result = attach_to_user(incoming, incoming.anonymous_applicant, account_with_user)

    assert result == AttachResult(application=incoming, discarded_draft=True)


def test_attaching_over_a_held_submission_reports_no_draft_discarded(
    account_with_user,
):
    incoming = _anonymous_draft_for("taken@example.com")
    held = CourseApplicationFactory(user=account_with_user, course=incoming.course)

    result = attach_to_user(incoming, incoming.anonymous_applicant, account_with_user)

    assert result == AttachResult(application=held, discarded_draft=False)


def test_attaching_to_an_account_holding_nothing_reports_no_draft_discarded(
    account_with_user,
):
    incoming = _anonymous_draft_for("taken@example.com")

    result = attach_to_user(incoming, incoming.anonymous_applicant, account_with_user)

    assert result == AttachResult(application=incoming, discarded_draft=False)


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
                attach_claimed_application(request, application, link_version=0)
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

    attach_claimed_application(rf.get("/"), application, link_version=0)

    squatter.refresh_from_db()
    assert squatter.has_usable_password() is False


def test_claiming_a_squatted_address_verifies_it(squatted_application, rf):
    application, squatter = squatted_application

    attach_claimed_application(rf.get("/"), application, link_version=0)

    address = EmailAddress.objects.get(user=squatter, email="victim@example.com")
    assert address.verified is True


def test_claiming_a_squatted_address_asks_for_a_new_password(squatted_application, rf):
    application, squatter = squatted_application

    outcome = attach_claimed_application(rf.get("/"), application, link_version=0)

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

    attach_claimed_application(rf.get("/"), application, link_version=0)

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

    outcome = attach_claimed_application(rf.get("/"), application, link_version=0)

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

    attach_claimed_application(rf.get("/"), application, link_version=0)

    user.refresh_from_db()
    assert user.has_usable_password() is False


def test_claiming_a_login_synced_address_verifies_the_one_row(
    login_synced_application, rf
):
    application, user = login_synced_application

    attach_claimed_application(rf.get("/"), application, link_version=0)

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

    outcome = attach_claimed_application(rf.get("/"), application, link_version=0)

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

    attach_claimed_application(rf.get("/"), application, link_version=0)

    assert EmailAddress.objects.filter(user=user).count() == 1


def test_claiming_a_mixed_case_unverified_address_verifies_that_row(
    mock_site_context, rf
):
    user = UserFactory(email="Ada.Lovelace@example.com")
    EmailAddressFactory(user=user, email="Ada.Lovelace@example.com", verified=False)
    application = _anonymous_application_for("ada.lovelace@example.com")

    attach_claimed_application(rf.get("/"), application, link_version=0)

    addresses = EmailAddress.objects.filter(user=user)
    assert [(a.email, a.verified) for a in addresses] == [
        ("Ada.Lovelace@example.com", True)
    ]


def test_an_operator_created_account_gains_a_verified_primary_address_when_claimed(
    mock_site_context, rf
):
    user = UserFactory(email="staffmade@example.com")
    application = _anonymous_application_for("staffmade@example.com")

    attach_claimed_application(rf.get("/"), application, link_version=0)

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
