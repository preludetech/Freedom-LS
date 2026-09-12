"""Admin tests.

`SignupAttribution` and `FirstTouchCount` are fully read-only. `ReferralCode`
is writable but never deletable, and `ReferralCodeHit` is read-only like the
first two.
"""

from __future__ import annotations

import pytest

from django.contrib import admin
from django.contrib.auth.models import Permission
from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.referral_tracking.admin import UNSAVED_MESSAGE, ReferralCodeAdmin
from freedom_ls.referral_tracking.codes import (
    GENERATED_CODE_ALPHABET,
    GENERATED_CODE_LENGTH,
)
from freedom_ls.referral_tracking.factories import (
    FirstTouchCountFactory,
    ReferralCodeFactory,
    ReferralCodeHitFactory,
    SignupAttributionFactory,
)
from freedom_ls.referral_tracking.models import (
    FirstTouchCount,
    ReferralCode,
    SignupAttribution,
)

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


# --- ReferralCode ------------------------------------------------------------


@pytest.fixture
def superuser_client(mock_site_context, db):
    """A user who can add, change and view every referral-tracking model.

    `has_delete_permission` on `ReferralCodeAdmin` and `ReferralCodeHitAdmin`
    always returns `False`, so even a superuser cannot delete through either
    admin — that refusal is what these tests exercise.
    """
    user = UserFactory(superuser=True)
    client = Client()
    client.force_login(user)
    return client


@pytest.fixture
def referral_code_admin_instance() -> ReferralCodeAdmin:
    return ReferralCodeAdmin(ReferralCode, admin.site)


def _referral_code_add_payload(**overrides: str) -> dict[str, str]:
    payload = {
        "code": "",
        "label": "Trade stand",
        "notes": "",
        "destination": "/courses/",
        "inactive_destination": "",
        "is_active": "on",
    }
    payload.update(overrides)
    return payload


@pytest.mark.django_db
def test_referral_code_add_with_blank_code_generates_one(superuser_client):
    response = superuser_client.post(
        reverse(f"admin:{APP_LABEL}_referralcode_add"), _referral_code_add_payload()
    )

    assert response.status_code == 302
    code = ReferralCode.objects.get(label="Trade stand")
    assert len(code.code) == GENERATED_CODE_LENGTH
    assert set(code.code) <= set(GENERATED_CODE_ALPHABET)


@pytest.mark.django_db
def test_referral_code_add_with_case_only_duplicate_is_a_form_error(
    superuser_client, mock_site_context
):
    ReferralCodeFactory(code="MrBeast")

    response = superuser_client.post(
        reverse(f"admin:{APP_LABEL}_referralcode_add"),
        _referral_code_add_payload(code="mrbeast"),
    )

    assert response.status_code == 200
    assert response.context["adminform"].form.errors


@pytest.mark.django_db
def test_referral_code_add_with_case_only_duplicate_reports_a_duplicate_code_error(
    superuser_client, mock_site_context
):
    ReferralCodeFactory(code="MrBeast")

    response = superuser_client.post(
        reverse(f"admin:{APP_LABEL}_referralcode_add"),
        _referral_code_add_payload(code="mrbeast"),
    )

    errors = response.context["adminform"].form.errors
    assert "code" in errors
    assert "constraint" not in errors["code"][0].lower()


@pytest.mark.django_db
def test_referral_code_add_with_exact_duplicate_reports_a_duplicate_code_error(
    superuser_client, mock_site_context
):
    ReferralCodeFactory(code="MrBeast")

    response = superuser_client.post(
        reverse(f"admin:{APP_LABEL}_referralcode_add"),
        _referral_code_add_payload(code="MrBeast"),
    )

    errors = response.context["adminform"].form.errors
    assert "code" in errors
    assert "constraint" not in errors["code"][0].lower()


@pytest.mark.django_db
def test_referral_code_change_form_does_not_render_code_as_an_input(
    superuser_client, mock_site_context
):
    code = ReferralCodeFactory(code="mrbeast")

    response = superuser_client.get(
        reverse(f"admin:{APP_LABEL}_referralcode_change", args=[code.pk])
    )

    assert 'name="code"' not in response.content.decode()


@pytest.mark.django_db
def test_referral_code_change_post_does_not_change_the_code(
    superuser_client, mock_site_context
):
    code = ReferralCodeFactory(code="mrbeast", destination="/courses/")
    url = reverse(f"admin:{APP_LABEL}_referralcode_change", args=[code.pk])

    response = superuser_client.post(
        url,
        {
            "code": "hacked",
            "label": code.label,
            "notes": "",
            "destination": code.destination,
            "inactive_destination": "",
            "is_active": "on",
        },
    )

    code.refresh_from_db()
    assert code.code == "mrbeast"
    assert response.status_code == 302


@pytest.mark.django_db
def test_referral_code_change_post_saves_when_the_stored_code_is_invalid(
    superuser_client, mock_site_context
):
    """A code written past `full_clean()` must not break its own change form.

    `code` is read-only on the change form, so it is excluded from the form's
    fields. `Model.full_clean()` runs `clean()` regardless of that exclusion,
    and a `ValidationError` keyed to an absent field makes `add_error` raise
    `ValueError` rather than rendering an error.
    """
    code = ReferralCodeFactory(code="has_underscore", destination="/courses/")
    url = reverse(f"admin:{APP_LABEL}_referralcode_change", args=[code.pk])

    response = superuser_client.post(
        url,
        {
            "code": "has_underscore",
            "label": "Renamed stand",
            "notes": "",
            "destination": code.destination,
            "inactive_destination": "",
            "is_active": "on",
        },
    )

    assert response.status_code == 302
    code.refresh_from_db()
    assert code.label == "Renamed stand"


@pytest.mark.django_db
def test_referral_code_change_form_renders_for_a_code_outside_the_url_pattern(
    superuser_client, mock_site_context
):
    """A code stored past `full_clean()` must not break `reverse()` in the

    read-only `go_url`/`d_url` fields when the change form renders.
    """
    code = ReferralCodeFactory(code="has_underscore", destination="/courses/")
    url = reverse(f"admin:{APP_LABEL}_referralcode_change", args=[code.pk])

    response = superuser_client.get(url)

    assert response.status_code == 200


@pytest.mark.django_db
def test_referral_code_add_with_a_reserved_code_is_a_field_error(
    superuser_client, mock_site_context
):
    response = superuser_client.post(
        reverse(f"admin:{APP_LABEL}_referralcode_add"),
        _referral_code_add_payload(code="admin"),
    )

    assert response.status_code == 200
    assert "code" in response.context["adminform"].form.errors


@pytest.mark.django_db
def test_referral_code_delete_returns_403(superuser_client, mock_site_context):
    code = ReferralCodeFactory()
    url = reverse(f"admin:{APP_LABEL}_referralcode_delete", args=[code.pk])

    response = superuser_client.post(url, {"post": "yes"})

    assert ReferralCode.objects.filter(pk=code.pk).exists()
    assert response.status_code == 403


@pytest.mark.django_db
def test_referral_code_changelist_offers_no_delete_selected_action(
    superuser_client, mock_site_context
):
    ReferralCodeFactory()

    response = superuser_client.get(
        reverse(f"admin:{APP_LABEL}_referralcode_changelist")
    )

    assert b"delete_selected" not in response.content


@pytest.mark.django_db
def test_deactivate_action_flips_the_selection_and_reports_the_count(
    superuser_client, mock_site_context
):
    first = ReferralCodeFactory(is_active=True)
    second = ReferralCodeFactory(is_active=True)

    response = superuser_client.post(
        reverse(f"admin:{APP_LABEL}_referralcode_changelist"),
        {
            "action": "deactivate_referral_codes",
            "_selected_action": [str(first.pk), str(second.pk)],
            "select_across": "0",
            "index": "0",
        },
        follow=True,
    )

    first.refresh_from_db()
    second.refresh_from_db()
    assert first.is_active is False
    assert second.is_active is False
    assert b"Deactivated 2 referral code(s)." in response.content


def test_the_change_form_loads_the_copy_button_stylesheet(
    referral_code_admin_instance,
):
    media = str(referral_code_admin_instance.media)

    assert "referral_tracking/css/copy_button.css" in media
    # Declaring css here is easy to get wrong in a way that silently drops the
    # base class's stylesheet, so pin that it is still merged in.
    assert "site_aware_models/css/admin.css" in media


@pytest.mark.django_db
def test_go_url_uses_the_codes_site_domain(
    mock_site_context, referral_code_admin_instance
):
    code = ReferralCodeFactory(code="mrbeast")

    html = referral_code_admin_instance.go_url(code)

    assert code.site.domain in html


@pytest.mark.django_db
def test_d_url_is_fully_uppercase(mock_site_context, referral_code_admin_instance):
    code = ReferralCodeFactory(code="mrbeast")

    html = referral_code_admin_instance.d_url(code)

    assert "MRBEAST" in html
    assert "mrbeast" not in html


@pytest.mark.django_db
def test_unsaved_referral_code_shows_the_unsaved_message(
    mock_site_context, referral_code_admin_instance, site
):
    unsaved = ReferralCode(site=site, code="temp", label="Temp", destination="/")

    assert referral_code_admin_instance.go_url(unsaved) == UNSAVED_MESSAGE
    assert referral_code_admin_instance.d_url(unsaved) == UNSAVED_MESSAGE
    assert referral_code_admin_instance.destination_preview(unsaved) == UNSAVED_MESSAGE
    assert (
        referral_code_admin_instance.inactive_destination_preview(unsaved)
        == UNSAVED_MESSAGE
    )


@pytest.mark.django_db
def test_destination_preview_matches_the_view_redirect(
    mock_site_context, referral_code_admin_instance
):
    code = ReferralCodeFactory(code="mrbeast", destination="/courses/")

    response = Client().get(f"/go/{code.code}")

    assert response.url == referral_code_admin_instance.destination_preview(code)


@pytest.mark.django_db
def test_inactive_destination_preview_matches_the_view_redirect(
    mock_site_context, referral_code_admin_instance
):
    code = ReferralCodeFactory(
        code="oldcode", is_active=False, inactive_destination="/retired/"
    )

    response = Client().get(f"/go/{code.code}")

    assert response.url == referral_code_admin_instance.inactive_destination_preview(
        code
    )


# --- ReferralCodeHit -----------------------------------------------------------


@pytest.mark.django_db
def test_referral_code_hit_admin_add_returns_403(superuser_client):
    response = superuser_client.get(reverse(f"admin:{APP_LABEL}_referralcodehit_add"))
    assert response.status_code == 403


@pytest.mark.django_db
def test_referral_code_hit_admin_change_returns_403(
    superuser_client, mock_site_context
):
    hit = ReferralCodeHitFactory()

    response = superuser_client.post(
        reverse(f"admin:{APP_LABEL}_referralcodehit_change", args=[hit.pk]), {}
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_referral_code_hit_admin_delete_returns_403(
    superuser_client, mock_site_context
):
    hit = ReferralCodeHitFactory()

    response = superuser_client.post(
        reverse(f"admin:{APP_LABEL}_referralcodehit_delete", args=[hit.pk]),
        {"post": "yes"},
    )

    assert response.status_code == 403
