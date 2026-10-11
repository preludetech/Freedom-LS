"""Tests for the applicant details form."""

from __future__ import annotations

import pytest

from django.http import QueryDict
from django.test import RequestFactory

from freedom_ls.accounts.factories import SiteSignupPolicyFactory
from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.course_applications"):
    pytest.skip("course_applications not installed", allow_module_level=True)

from freedom_ls.course_applications.factories import AnonymousApplicantFactory
from freedom_ls.course_applications.forms import (
    HONEYPOT_APPLICATION_MESSAGE,
    ApplicantDetailsForm,
)
from freedom_ls.course_applications.models import AnonymousApplicant

pytestmark = pytest.mark.django_db


@pytest.fixture
def request_for_site(mock_site_context, rf: RequestFactory):
    request = rf.post("/")
    request._cached_site = mock_site_context
    return request


def _form(request, **data: str) -> ApplicantDetailsForm:
    payload = {"email": "ada@example.com", "first_name": "Ada", "last_name": "L"}
    payload.update(data)
    instance = AnonymousApplicant(course=AnonymousApplicantFactory().course)
    query = QueryDict(mutable=True)
    query.update(payload)
    return ApplicantDetailsForm(query, request=request, instance=instance)


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
