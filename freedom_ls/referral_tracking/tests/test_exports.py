"""Tests for the CSV export shared by the referral-tracking admins."""

from __future__ import annotations

import codecs
import csv
import io

import pytest

from django.contrib import admin
from django.contrib.auth.models import Permission
from django.db.models import QuerySet
from django.http import HttpResponse
from django.test import Client, RequestFactory
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.referral_tracking.admin import SignupAttributionAdmin
from freedom_ls.referral_tracking.exports import export_as_csv
from freedom_ls.referral_tracking.factories import SignupAttributionFactory
from freedom_ls.referral_tracking.models import SignupAttribution

APP_LABEL = "freedom_ls_referral_tracking"


def _export(queryset: QuerySet) -> HttpResponse:
    request = RequestFactory().get("/")
    modeladmin = SignupAttributionAdmin(SignupAttribution, admin.site)
    return export_as_csv(modeladmin, request, queryset)


@pytest.fixture
def staff_client(mock_site_context, db):
    """Staff user with permission to view and export SignupAttribution rows."""
    user = UserFactory(staff=True)
    permission = Permission.objects.get(
        content_type__app_label=APP_LABEL, codename="view_signupattribution"
    )
    user.user_permissions.add(permission)
    client = Client()
    client.force_login(user)
    return client


@pytest.mark.django_db
def test_export_body_starts_with_utf8_bom(mock_site_context):
    SignupAttributionFactory()

    response = _export(SignupAttribution.objects.all())

    assert response.content.startswith(codecs.BOM_UTF8)


@pytest.mark.django_db
def test_export_escapes_a_formula_looking_campaign(mock_site_context):
    SignupAttributionFactory(utm_campaign="=1+1")

    response = _export(SignupAttribution.objects.all())

    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
    header, row = rows[0], rows[1]
    assert row[header.index("utm_campaign")] == "'=1+1"


@pytest.mark.django_db
def test_export_quotes_a_value_containing_a_comma(mock_site_context):
    SignupAttributionFactory(referer="https://example.com/a,b")

    response = _export(SignupAttribution.objects.all())
    body = response.content.decode("utf-8-sig")

    rows = list(csv.reader(io.StringIO(body)))
    header, row = rows[0], rows[1]
    assert row[header.index("referer")] == "https://example.com/a,b"
    assert '"https://example.com/a,b"' in body


@pytest.mark.django_db
def test_export_header_includes_fields_the_changelist_omits(mock_site_context):
    SignupAttributionFactory()

    response = _export(SignupAttribution.objects.all())

    header = response.content.decode("utf-8-sig").splitlines()[0]
    assert "gclid" in header
    assert "client_ip" in header
    assert "user_agent" in header


@pytest.mark.django_db
def test_export_writes_signed_up_at_as_iso_8601(mock_site_context):
    attribution = SignupAttributionFactory()

    response = _export(SignupAttribution.objects.all())

    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
    header, row = rows[0], rows[1]
    assert row[header.index("signed_up_at")] == attribution.signed_up_at.isoformat()


@pytest.mark.django_db
def test_export_action_on_filtered_changelist_returns_csv(staff_client):
    kept = SignupAttributionFactory(utm_source="google")
    SignupAttributionFactory(utm_source="direct")

    response = staff_client.post(
        reverse(f"admin:{APP_LABEL}_signupattribution_changelist"),
        {
            "action": "export_as_csv",
            "select_across": "1",
            "index": "0",
            "_selected_action": [str(kept.pk)],
        },
    )

    assert response["Content-Type"].startswith("text/csv")
