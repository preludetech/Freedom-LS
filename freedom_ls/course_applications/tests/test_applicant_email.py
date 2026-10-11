"""Tests for the applicant email helpers."""

from __future__ import annotations

import pytest

from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.course_applications"):
    pytest.skip("course_applications not installed", allow_module_level=True)

from freedom_ls.course_applications.applicant_email import (
    email_rate_limit_key,
    normalise_email,
)


def test_normalise_email_strips_and_lowercases():
    assert normalise_email("  Ada@Example.COM\n") == "ada@example.com"


@pytest.mark.django_db
def test_email_rate_limit_key_is_site_pk_and_normalised_email(site):
    key = email_rate_limit_key(site, "  Ada@Example.COM ")

    assert key == f"{site.pk}:ada@example.com"
