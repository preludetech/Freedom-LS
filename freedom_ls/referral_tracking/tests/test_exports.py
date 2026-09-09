"""Tests for the CSV export on the referral-tracking admins."""

from __future__ import annotations

import codecs
import csv
import io

import pytest

from django.contrib.auth.models import Permission
from django.http import HttpResponse
from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.referral_tracking.factories import (
    FirstTouchCountFactory,
    SignupAttributionFactory,
)
from freedom_ls.referral_tracking.resources import (
    FirstTouchCountResource,
    SignupAttributionResource,
)
from freedom_ls.site_aware_models.admin_exports import (
    IsoDateTimeWidget,
    IsoDateWidget,
)

APP_LABEL = "freedom_ls_referral_tracking"


@pytest.fixture
def staff_client(mock_site_context, db):
    """Staff user with permission to view both referral-tracking models."""
    user = UserFactory(staff=True)
    permissions = Permission.objects.filter(
        content_type__app_label=APP_LABEL,
        codename__in=["view_signupattribution", "view_firsttouchcount"],
    )
    user.user_permissions.add(*permissions)
    client = Client()
    client.force_login(user)
    return client


@pytest.fixture
def unprivileged_staff_client(mock_site_context, db):
    """Staff user with no permission on either referral-tracking model."""
    user = UserFactory(staff=True)
    client = Client()
    client.force_login(user)
    return client


def _export_selected(
    client: Client, model_name: str, pks: list[str], query: str = ""
) -> HttpResponse:
    response: HttpResponse = client.post(
        reverse(f"admin:{APP_LABEL}_{model_name}_changelist") + query,
        {
            "action": "export_admin_action",
            "select_across": "1",
            "index": "0",
            "_selected_action": pks,
        },
    )
    return response


def _rows(response: HttpResponse) -> tuple[list[str], list[list[str]]]:
    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
    return rows[0], rows[1:]


@pytest.mark.django_db
def test_export_body_starts_with_utf8_bom(staff_client):
    row = SignupAttributionFactory()

    response = _export_selected(staff_client, "signupattribution", [str(row.pk)])

    assert response.content.startswith(codecs.BOM_UTF8)


@pytest.mark.django_db
def test_export_escapes_a_formula_looking_campaign(staff_client):
    row = SignupAttributionFactory(utm_campaign="=1+1")

    response = _export_selected(staff_client, "signupattribution", [str(row.pk)])

    header, (values,) = _rows(response)
    assert values[header.index("utm_campaign")] == "'=1+1"


@pytest.mark.django_db
def test_export_quotes_a_value_containing_a_comma(staff_client):
    row = SignupAttributionFactory(referer="https://example.com/a,b")

    response = _export_selected(staff_client, "signupattribution", [str(row.pk)])
    body = response.content.decode("utf-8-sig")

    header, (values,) = _rows(response)
    assert values[header.index("referer")] == "https://example.com/a,b"
    assert '"https://example.com/a,b"' in body


@pytest.mark.django_db
def test_export_header_includes_fields_the_changelist_omits(staff_client):
    row = SignupAttributionFactory()

    response = _export_selected(staff_client, "signupattribution", [str(row.pk)])

    header, _ = _rows(response)
    assert "gclid" in header
    assert "client_ip" in header
    assert "user_agent" in header


@pytest.mark.django_db
def test_export_omits_site(staff_client):
    row = SignupAttributionFactory()

    response = _export_selected(staff_client, "signupattribution", [str(row.pk)])

    header, _ = _rows(response)
    assert "site" not in header


@pytest.mark.django_db
def test_export_writes_signed_up_at_as_iso_8601(staff_client):
    row = SignupAttributionFactory()

    response = _export_selected(staff_client, "signupattribution", [str(row.pk)])

    header, (values,) = _rows(response)
    assert values[header.index("signed_up_at")] == row.signed_up_at.isoformat()


@pytest.mark.django_db
def test_export_writes_user_as_email(staff_client):
    row = SignupAttributionFactory()

    response = _export_selected(staff_client, "signupattribution", [str(row.pk)])

    header, (values,) = _rows(response)
    assert values[header.index("user")] == row.user.email


@pytest.mark.django_db
def test_export_action_on_filtered_changelist_returns_only_matching_rows(
    staff_client,
):
    kept = SignupAttributionFactory(utm_source="google")
    SignupAttributionFactory(utm_source="direct")

    response = _export_selected(
        staff_client, "signupattribution", [str(kept.pk)], "?utm_source=google"
    )

    assert response["Content-Type"].startswith("text/csv")
    _, rows = _rows(response)
    assert len(rows) == 1
    assert b"direct" not in response.content


@pytest.mark.django_db
def test_export_button_downloads_the_filtered_changelist(staff_client):
    SignupAttributionFactory(utm_source="google")
    SignupAttributionFactory(utm_source="direct")

    response = staff_client.get(
        reverse(f"admin:{APP_LABEL}_signupattribution_export") + "?utm_source=google"
    )

    assert response["Content-Type"].startswith("text/csv")
    _, rows = _rows(response)
    assert len(rows) == 1


@pytest.mark.django_db
def test_export_url_returns_403_without_view_permission(unprivileged_staff_client):
    SignupAttributionFactory()

    response = unprivileged_staff_client.get(
        reverse(f"admin:{APP_LABEL}_signupattribution_export")
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_export_action_is_offered_to_a_viewer(staff_client):
    SignupAttributionFactory()

    response = staff_client.get(
        reverse(f"admin:{APP_LABEL}_signupattribution_changelist")
    )

    assert b"export_admin_action" in response.content


@pytest.mark.django_db
def test_first_touch_count_export_escapes_and_writes_iso_day(staff_client):
    row = FirstTouchCountFactory(utm_campaign="=1+1")

    response = _export_selected(staff_client, "firsttouchcount", [str(row.pk)])

    assert response["Content-Type"].startswith("text/csv")
    header, (values,) = _rows(response)
    assert values[header.index("day")] == row.day.isoformat()
    assert values[header.index("utm_campaign")] == "'=1+1"


def test_resources_map_date_fields_to_iso_widgets():
    assert isinstance(
        SignupAttributionResource.fields["signed_up_at"].widget, IsoDateTimeWidget
    )
    assert isinstance(FirstTouchCountResource.fields["day"].widget, IsoDateWidget)
    assert "site" not in SignupAttributionResource.fields
