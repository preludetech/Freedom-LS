"""Tests for the course_applications forms."""

from __future__ import annotations

import pytest

from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.course_applications"):
    pytest.skip("course_applications not installed", allow_module_level=True)

from freedom_ls.course_applications.forms import ApplicantEmailForm


def test_email_is_lowercased():
    form = ApplicantEmailForm({"email": "Pat@Example.COM"})

    assert form.is_valid()
    assert form.cleaned_data["email"] == "pat@example.com"


def test_honeypot_trip_rejects_the_form_with_the_application_wording():
    form = ApplicantEmailForm({"email": "pat@example.com", "fax_number": "bot"})

    assert not form.is_valid()
    assert form.non_field_errors() == [
        "We couldn't process this application. If you used autofill or a "
        "password manager, please try typing your email address in by hand."
    ]
