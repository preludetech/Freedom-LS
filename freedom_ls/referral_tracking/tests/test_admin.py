"""Admin tests — `SignupAttribution` and `FirstTouchCount` are fully read-only."""

from __future__ import annotations

import pytest

from django.contrib.auth.models import Permission
from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.referral_tracking.factories import (
    FirstTouchCountFactory,
    SignupAttributionFactory,
)
from freedom_ls.referral_tracking.models import FirstTouchCount, SignupAttribution

APP_LABEL = "freedom_ls_referral_tracking"


def _grant_view_permissions(user: User) -> None:
    permissions = Permission.objects.filter(
        content_type__app_label=APP_LABEL,
        codename__in=["view_signupattribution", "view_firsttouchcount"],
    )
    user.user_permissions.add(*permissions)


@pytest.fixture
def staff_client(mock_site_context, db):
    """Staff user granted view-only permission on both referral-tracking models."""
    user = UserFactory(staff=True)
    _grant_view_permissions(user)
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


@pytest.mark.django_db
def test_signup_attribution_changelist_returns_200_for_viewer(staff_client):
    response = staff_client.get(
        reverse(f"admin:{APP_LABEL}_signupattribution_changelist")
    )
    assert response.status_code == 200


@pytest.mark.django_db
def test_first_touch_count_changelist_returns_200_for_viewer(staff_client):
    response = staff_client.get(
        reverse(f"admin:{APP_LABEL}_firsttouchcount_changelist")
    )
    assert response.status_code == 200


@pytest.mark.django_db
def test_signup_attribution_add_returns_403(staff_client):
    response = staff_client.get(reverse(f"admin:{APP_LABEL}_signupattribution_add"))
    assert response.status_code == 403


@pytest.mark.django_db
def test_first_touch_count_add_returns_403(staff_client):
    response = staff_client.get(reverse(f"admin:{APP_LABEL}_firsttouchcount_add"))
    assert response.status_code == 403


@pytest.mark.django_db
def test_signup_attribution_change_does_not_persist_modification(
    staff_client, mock_site_context
):
    attribution = SignupAttributionFactory(utm_campaign="spring-sale")
    url = reverse(f"admin:{APP_LABEL}_signupattribution_change", args=[attribution.pk])

    response = staff_client.post(url, {"utm_campaign": "tampered"})

    attribution.refresh_from_db()
    assert attribution.utm_campaign == "spring-sale"
    assert response.status_code != 302


@pytest.mark.django_db
def test_first_touch_count_change_does_not_persist_modification(
    staff_client, mock_site_context
):
    tally = FirstTouchCountFactory(count=1)
    url = reverse(f"admin:{APP_LABEL}_firsttouchcount_change", args=[tally.pk])

    response = staff_client.post(url, {"count": 999})

    tally.refresh_from_db()
    assert tally.count == 1
    assert response.status_code != 302


@pytest.mark.django_db
def test_signup_attribution_delete_keeps_row(staff_client, mock_site_context):
    attribution = SignupAttributionFactory()
    url = reverse(f"admin:{APP_LABEL}_signupattribution_delete", args=[attribution.pk])

    response = staff_client.post(url, {"post": "yes"})

    assert SignupAttribution.objects.filter(pk=attribution.pk).exists()
    assert response.status_code == 403


@pytest.mark.django_db
def test_first_touch_count_delete_keeps_row(staff_client, mock_site_context):
    tally = FirstTouchCountFactory()
    url = reverse(f"admin:{APP_LABEL}_firsttouchcount_delete", args=[tally.pk])

    response = staff_client.post(url, {"post": "yes"})

    assert FirstTouchCount.objects.filter(pk=tally.pk).exists()
    assert response.status_code == 403


@pytest.mark.django_db
def test_signup_attribution_changelist_returns_403_without_permission(
    unprivileged_staff_client,
):
    response = unprivileged_staff_client.get(
        reverse(f"admin:{APP_LABEL}_signupattribution_changelist")
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_first_touch_count_changelist_returns_403_without_permission(
    unprivileged_staff_client,
):
    response = unprivileged_staff_client.get(
        reverse(f"admin:{APP_LABEL}_firsttouchcount_changelist")
    )
    assert response.status_code == 403
