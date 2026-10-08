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
