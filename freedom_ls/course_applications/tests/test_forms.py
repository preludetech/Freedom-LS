"""Tests for the course_applications forms."""

from __future__ import annotations

import pytest

from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.course_applications"):
    pytest.skip("course_applications not installed", allow_module_level=True)

from freedom_ls.course_applications.forms import ApplicantDetailsForm


def test_email_is_lowercased():
    form = ApplicantDetailsForm({"first_name": "Pat", "email": "Pat@Example.COM"})

    assert form.is_valid()
    assert form.cleaned_data["email"] == "pat@example.com"


def test_honeypot_trip_rejects_the_form_with_the_application_wording():
    form = ApplicantDetailsForm(
        {"first_name": "Pat", "email": "pat@example.com", "fax_number": "bot"}
    )

    assert not form.is_valid()
    assert form.non_field_errors() == [
        "We couldn't process this application. If you used autofill or a "
        "password manager, please try typing your details in by hand."
    ]


def test_ask_for_limits_the_form_to_the_details_named():
    form = ApplicantDetailsForm({"email": "pat@example.com"}, ask_for=("email",))

    assert list(form.fields) == ["fax_number", "email"]
    assert form.is_valid()
    assert form.details == {"email": "pat@example.com"}


def test_first_name_is_required_when_the_site_requires_a_name(settings):
    settings.REQUIRE_NAME = True

    form = ApplicantDetailsForm({"email": "pat@example.com"})

    assert not form.is_valid()
    assert "first_name" in form.errors


def test_first_name_is_optional_when_the_site_does_not_require_a_name(settings):
    settings.REQUIRE_NAME = False

    form = ApplicantDetailsForm({"email": "pat@example.com"})

    assert form.is_valid()
    assert form.fields["first_name"].label == "First name (optional)"


def test_details_omits_the_honeypot():
    form = ApplicantDetailsForm({"first_name": "Pat", "email": "pat@example.com"})

    assert form.is_valid()
    assert set(form.details) == {"first_name", "last_name", "email"}
