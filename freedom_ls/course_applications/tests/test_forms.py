"""Tests for the applicant details form."""

from __future__ import annotations

import pytest

from django.http import QueryDict
from django.test import RequestFactory
from django.utils import timezone

from freedom_ls.accounts.factories import SiteSignupPolicyFactory, UserFactory
from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.course_applications"):
    pytest.skip("course_applications not installed", allow_module_level=True)

from freedom_ls.course_applications.factories import AnonymousApplicantFactory
from freedom_ls.course_applications.forms import (
    HONEYPOT_APPLICATION_MESSAGE,
    ApplicantDetailsForm,
    ApplicantEmailForm,
)
from freedom_ls.course_applications.models import AnonymousApplicant

pytestmark = pytest.mark.django_db


@pytest.fixture
def request_for_site(mock_site_context, rf: RequestFactory):
    request = rf.post("/")
    request._cached_site = mock_site_context
    return request


def _query(**data: str) -> QueryDict:
    payload = {"email": "ada@example.com", "first_name": "Ada", "last_name": "L"}
    payload.update(data)
    query = QueryDict(mutable=True)
    query.update(payload)
    return query


def _form(request, **data: str) -> ApplicantDetailsForm:
    instance = AnonymousApplicant(course=AnonymousApplicantFactory().course)
    return ApplicantDetailsForm(_query(**data), request=request, instance=instance)


def test_form_refuses_a_filled_honeypot_with_the_application_message(request_for_site):
    form = _form(request_for_site, fax_number="bot")

    assert form.is_valid() is False
    assert form.non_field_errors() == [str(HONEYPOT_APPLICATION_MESSAGE)]


def test_first_name_is_optional_when_the_policy_does_not_require_a_name(
    request_for_site, site
):
    SiteSignupPolicyFactory(site=site, require_name=False)

    form = _form(request_for_site, first_name="")

    assert form.is_valid() is True


def test_first_name_is_required_by_default(request_for_site):
    form = _form(request_for_site, first_name="")

    assert form.is_valid() is False


def test_email_is_stored_stripped_and_lowercased(request_for_site):
    form = _form(request_for_site, email="  Ada@Example.COM ")

    form.is_valid()

    assert form.cleaned_data["email"] == "ada@example.com"


def test_closed_signups_do_not_change_validation(request_for_site, site):
    SiteSignupPolicyFactory(site=site, allow_signups=False)

    form = _form(request_for_site)

    assert form.is_valid() is True


@pytest.fixture
def terms_required(site, legal_repo_mock):
    SiteSignupPolicyFactory(site=site, require_terms_acceptance=True)


def _consent(**overrides: str) -> dict[str, str]:
    data = {"accept_terms": "on", "accept_privacy": "on"}
    data.update(overrides)
    return data


def test_form_has_both_consent_checkboxes_when_the_policy_requires_terms(
    request_for_site, terms_required
):
    form = _form(request_for_site)

    assert {"accept_terms", "accept_privacy"} <= set(form.fields)


def test_form_without_the_checkboxes_ticked_is_invalid(
    request_for_site, terms_required
):
    form = _form(request_for_site)

    assert form.is_valid() is False
    assert set(form.errors) == {"accept_terms", "accept_privacy"}


def test_save_stores_the_document_versions_and_git_hashes(
    request_for_site, terms_required
):
    form = _form(request_for_site, **_consent())
    assert form.is_valid()

    applicant = form.save(commit=False)

    assert applicant.terms_version == "1.5"
    assert len(applicant.terms_git_hash) == 40
    assert applicant.privacy_version == "1.5"
    assert len(applicant.privacy_git_hash) == 40


def test_save_stores_the_client_ip(request_for_site, terms_required, settings):
    settings.TRUSTED_PROXY_IP_HEADER = None
    request_for_site.META["REMOTE_ADDR"] = "203.0.113.7"
    form = _form(request_for_site, **_consent())
    assert form.is_valid()

    applicant = form.save(commit=False)

    assert applicant.consent_ip_address == "203.0.113.7"


def test_save_stores_when_consent_was_given(request_for_site, terms_required):
    form = _form(request_for_site, **_consent())
    assert form.is_valid()

    applicant = form.save(commit=False)

    assert applicant.consented_at is not None


def test_form_without_a_terms_policy_has_no_consent_field(request_for_site, site):
    SiteSignupPolicyFactory(site=site, require_terms_acceptance=False)

    form = _form(request_for_site)

    assert "accept_terms" not in form.fields
    assert "accept_privacy" not in form.fields


def test_save_without_a_terms_policy_leaves_the_evidence_blank(request_for_site, site):
    SiteSignupPolicyFactory(site=site, require_terms_acceptance=False)
    form = _form(request_for_site)
    assert form.is_valid()

    applicant = form.save(commit=False)

    assert applicant.terms_version == ""
    assert applicant.consent_ip_address is None
    assert applicant.consented_at is None


def _email_form(request, **data: str) -> ApplicantEmailForm:
    query = QueryDict(mutable=True)
    query.update({"email": "ada@example.com", **data})
    return ApplicantEmailForm(query, request=request)


def test_email_form_normalises_the_address(request_for_site):
    form = _email_form(request_for_site, email="  Ada@Example.COM ")

    assert form.is_valid() is True
    assert form.cleaned_data["email"] == "ada@example.com"


def test_email_form_refuses_a_filled_honeypot_with_the_application_message(
    request_for_site,
):
    form = _email_form(request_for_site, fax_number="bot")

    assert form.is_valid() is False
    assert form.non_field_errors() == [str(HONEYPOT_APPLICATION_MESSAGE)]


def test_details_form_does_not_rerender_a_filled_honeypot_value(request_for_site):
    form = _form(request_for_site, fax_number="bot")

    assert "value=" not in str(form["fax_number"])


def test_email_form_does_not_rerender_a_filled_honeypot_value(request_for_site):
    form = _email_form(request_for_site, fax_number="bot")

    assert "value=" not in str(form["fax_number"])


def test_email_form_refuses_an_invalid_address(request_for_site):
    form = _email_form(request_for_site, email="not-an-address")

    assert form.is_valid() is False
    assert "email" in form.errors


def test_saving_an_existing_applicant_keeps_a_claim_that_landed_meanwhile(
    request_for_site,
):
    """The form holds the applicant as loaded before the claim; its save must
    not write that stale `user` and `claimed_at` back over the claim."""
    applicant = AnonymousApplicantFactory(email="ada@example.com", first_name="Ada")
    form = ApplicantDetailsForm(
        _query(email="ada@example.com", first_name="Mary", last_name="L"),
        request=request_for_site,
        instance=applicant,
    )
    assert form.is_valid()
    claimed = AnonymousApplicant.objects.get(pk=applicant.pk)
    claimed.user = UserFactory()
    claimed.claimed_at = timezone.now()
    claimed.save(update_fields=["user", "claimed_at"])

    form.save()

    applicant.refresh_from_db()
    assert (applicant.first_name, applicant.user, applicant.claimed_at) == (
        "Mary",
        claimed.user,
        claimed.claimed_at,
    )


def test_saving_an_existing_applicant_leaves_the_address_to_the_view(
    request_for_site,
):
    """The address of an existing applicant changes only through
    `update_applicant_email`, so the form's own save never writes it."""
    applicant = AnonymousApplicantFactory(email="ada@example.com")
    form = ApplicantDetailsForm(
        _query(email="new@example.com", first_name="Ada", last_name="L"),
        request=request_for_site,
        instance=applicant,
    )
    assert form.is_valid()

    form.save()

    applicant.refresh_from_db()
    assert applicant.email == "ada@example.com"
