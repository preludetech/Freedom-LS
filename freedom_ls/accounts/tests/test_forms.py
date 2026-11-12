"""Tests for `SiteAwareSignupForm`."""

from __future__ import annotations

import io
import logging
import re

import pytest
from allauth.core.context import request_context
from PIL import Image

from django import forms
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import SiteSignupPolicyFactory, UserFactory
from freedom_ls.accounts.forms import (
    SiteAwareSignupForm,
    UserForm,
    accepted_legal_docs,
    apply_signup_name_policy,
    honeypot_field,
    reject_honeypot,
    tripped_honeypot,
)
from freedom_ls.accounts.models import LegalConsent
from freedom_ls.accounts.tests.profile_picture_samples import (
    gif_bytes,
    jpeg_bytes,
    truncated_jpeg_bytes,
)
from freedom_ls.accounts.validators import UNREADABLE, WRONG_TYPE

User = get_user_model()


@pytest.fixture
def allauth_request_ctx(mock_site_context, rf):
    """Bind a request to allauth's context for the duration of a test."""
    request = rf.get("/")
    request._cached_site = mock_site_context
    with request_context(request):
        yield request


@pytest.mark.django_db
def test_first_name_required_by_default(allauth_request_ctx, mock_site_context):
    """Default policy (or no policy row) → first_name required."""
    form = SiteAwareSignupForm()
    assert form.fields["first_name"].required is True


@pytest.mark.django_db
def test_first_name_optional_when_policy_disables_require_name(
    allauth_request_ctx, mock_site_context, site
):
    SiteSignupPolicyFactory(site=site, require_name=False)

    form = SiteAwareSignupForm()
    assert form.fields["first_name"].required is False


@pytest.mark.django_db
def test_first_name_optional_from_settings_default_when_no_policy(
    allauth_request_ctx, mock_site_context, settings
):
    """settings.REQUIRE_NAME=False with no policy → first_name optional."""
    settings.REQUIRE_NAME = False

    form = SiteAwareSignupForm()
    assert form.fields["first_name"].required is False


@pytest.mark.django_db
def test_first_name_required_from_settings_default_when_no_policy(
    allauth_request_ctx, mock_site_context, settings
):
    """settings.REQUIRE_NAME=True with no policy → first_name required."""
    settings.REQUIRE_NAME = True

    form = SiteAwareSignupForm()
    assert form.fields["first_name"].required is True


@pytest.mark.django_db
def test_policy_require_name_overrides_settings_default(
    allauth_request_ctx, mock_site_context, site, settings
):
    """A per-site policy with require_name=True overrides REQUIRE_NAME=False."""
    settings.REQUIRE_NAME = False
    SiteSignupPolicyFactory(site=site, require_name=True)

    form = SiteAwareSignupForm()
    assert form.fields["first_name"].required is True


@pytest.mark.django_db
def test_form_adds_consent_checkboxes_when_required_and_docs_present(
    allauth_request_ctx, mock_site_context, site, legal_repo_mock
):
    SiteSignupPolicyFactory(site=site, require_terms_acceptance=True)

    form = SiteAwareSignupForm()
    assert "accept_terms" in form.fields
    assert "accept_privacy" in form.fields
    assert form.fields["accept_terms"].required is True
    assert form.fields["accept_privacy"].required is True


@pytest.mark.django_db
def test_form_adds_consent_checkboxes_from_settings_default_when_no_policy(
    allauth_request_ctx, mock_site_context, legal_repo_mock, settings
):
    """When no SiteSignupPolicy exists for the site, settings.REQUIRE_TERMS_ACCEPTANCE
    drives whether consent checkboxes are added."""
    settings.REQUIRE_TERMS_ACCEPTANCE = True

    form = SiteAwareSignupForm()
    assert "accept_terms" in form.fields
    assert "accept_privacy" in form.fields


@pytest.mark.django_db
def test_form_omits_consent_checkboxes_when_settings_default_false(
    allauth_request_ctx, mock_site_context, legal_repo_mock, settings
):
    """settings.REQUIRE_TERMS_ACCEPTANCE=False with no policy → no checkboxes."""
    settings.REQUIRE_TERMS_ACCEPTANCE = False

    form = SiteAwareSignupForm()
    assert "accept_terms" not in form.fields
    assert "accept_privacy" not in form.fields


@pytest.mark.django_db
def test_policy_overrides_settings_default(
    allauth_request_ctx, mock_site_context, site, legal_repo_mock, settings
):
    """A per-site policy with require_terms_acceptance=False overrides
    a True global setting."""
    settings.REQUIRE_TERMS_ACCEPTANCE = True
    SiteSignupPolicyFactory(site=site, require_terms_acceptance=False)

    form = SiteAwareSignupForm()
    assert "accept_terms" not in form.fields
    assert "accept_privacy" not in form.fields


@pytest.mark.django_db
def test_form_does_not_add_checkboxes_when_docs_missing(
    allauth_request_ctx, mock_site_context, site, mock_legal_blobs, caplog
):
    """When `require_terms_acceptance=True` but no docs resolve, the form
    omits the checkbox rather than rendering a broken link."""
    # No blobs registered → all lookups raise FileNotFoundError.
    SiteSignupPolicyFactory(site=site, require_terms_acceptance=True)

    with caplog.at_level(logging.WARNING):
        form = SiteAwareSignupForm()

    assert "accept_terms" not in form.fields
    assert "accept_privacy" not in form.fields
    assert any("no terms doc" in r.message for r in caplog.records)


@pytest.mark.django_db
def test_custom_signup_records_consents(
    allauth_request_ctx, mock_site_context, site, legal_repo_mock, settings
):
    settings.TRUSTED_PROXY_IP_HEADER = None
    SiteSignupPolicyFactory(site=site, require_terms_acceptance=True)

    form = SiteAwareSignupForm()
    form.cleaned_data = {
        "accept_terms": True,
        "accept_privacy": True,
    }

    user = UserFactory()
    request = allauth_request_ctx
    request.META["REMOTE_ADDR"] = "203.0.113.99"

    form.custom_signup(request, user)

    consents = list(LegalConsent.objects.filter(user=user).order_by("document_type"))
    assert len(consents) == 2
    consent_by_type = {c.document_type: c for c in consents}
    assert consent_by_type["privacy"].document_version == "1.5"
    assert consent_by_type["terms"].document_version == "1.5"
    assert consent_by_type["terms"].ip_address == "203.0.113.99"
    assert consent_by_type["terms"].consent_method == "signup_checkbox"
    assert consent_by_type["terms"].site == site


@pytest.mark.django_db
def test_custom_signup_records_nothing_when_no_consent_fields(
    allauth_request_ctx, mock_site_context, site, legal_repo_mock
):
    """If no consent fields are present (policy not requiring them), no rows."""
    SiteSignupPolicyFactory(site=site, require_terms_acceptance=False)

    form = SiteAwareSignupForm()
    form.cleaned_data = {}

    user = UserFactory()

    form.custom_signup(allauth_request_ctx, user)

    assert LegalConsent.objects.filter(user=user).count() == 0


@pytest.mark.django_db
def test_signup_view_renders_each_consent_checkbox_once(
    mock_site_context, site, legal_repo_mock
):
    """Regression for Bug 1 in better-registration QA report.

    When the policy requires consent and both legal docs resolve, the
    signup page must render exactly one checkbox per consent — not
    duplicates from both `{% element fields %}` and the linked-label
    block.
    """
    SiteSignupPolicyFactory(site=site, require_terms_acceptance=True)

    response = Client().get(reverse("account_signup"))
    assert response.status_code == 200
    body = response.content.decode()

    assert body.count('name="accept_terms"') == 1
    assert body.count('name="accept_privacy"') == 1

    terms_url = reverse("accounts:legal_doc", kwargs={"doc_type": "terms"})
    privacy_url = reverse("accounts:legal_doc", kwargs={"doc_type": "privacy"})
    assert f'href="{terms_url}"' in body
    assert f'href="{privacy_url}"' in body


# Substrings of field names that browsers and password managers autofill. A
# honeypot whose name contains one of these gets filled for real people.
AUTOFILL_NAME_FRAGMENTS = [
    "name",
    "email",
    "mail",
    "website",
    "url",
    "homepage",
    "company",
    "organization",
    "organisation",
    "phone",
    "tel",
    "mobile",
    "address",
    "street",
    "city",
    "zip",
    "postal",
    "country",
    "user",
    "login",
    "password",
]

HONEYPOT_FIELD = "fax_number"
BOT_VALUE = "i-am-a-bot"


def _signup_data(**overrides: str) -> dict[str, str]:
    data = {
        "email": "honeypot@example.com",
        "password1": "Sup3rSecretPass!",  # pragma: allowlist secret
        "password2": "Sup3rSecretPass!",  # pragma: allowlist secret
        "first_name": "Test",
        "last_name": "Person",
        "accept_terms": "on",
        "accept_privacy": "on",
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
def test_honeypot_is_the_only_hidden_field(allauth_request_ctx, mock_site_context):
    form = SiteAwareSignupForm()

    assert [field.name for field in form.hidden_fields()] == [HONEYPOT_FIELD]


@pytest.mark.django_db
def test_honeypot_name_is_not_one_browsers_autofill(
    allauth_request_ctx, mock_site_context
):
    """Regression: `_hp` sat next to `last_name` and got filled with the surname."""
    form = SiteAwareSignupForm()

    for field in form.hidden_fields():
        assert not field.name.startswith("_")
        for fragment in AUTOFILL_NAME_FRAGMENTS:
            assert fragment not in field.name.lower()


@pytest.mark.django_db
def test_honeypot_rejects_submission_with_form_level_error(
    allauth_request_ctx, mock_site_context
):
    form = SiteAwareSignupForm(data=_signup_data(**{HONEYPOT_FIELD: BOT_VALUE}))

    assert form.is_valid() is False
    assert form.non_field_errors()
    assert set(form.errors) == {"__all__"}


@pytest.mark.django_db
def test_honeypot_trip_logs_one_warning_without_pii(
    allauth_request_ctx, mock_site_context, settings, caplog
):
    settings.TRUSTED_PROXY_IP_HEADER = None
    allauth_request_ctx.META["REMOTE_ADDR"] = "203.0.113.7"
    form = SiteAwareSignupForm(data=_signup_data(**{HONEYPOT_FIELD: BOT_VALUE}))

    with caplog.at_level(logging.WARNING, logger="freedom_ls.accounts.forms"):
        form.is_valid()

    records = [r for r in caplog.records if r.name == "freedom_ls.accounts.forms"]
    assert len(records) == 1
    message = records[0].getMessage()
    assert records[0].levelno == logging.WARNING
    assert mock_site_context.domain in message
    assert "203.0.113.7" in message
    assert "honeypot@example.com" not in message
    assert BOT_VALUE not in message


@pytest.mark.django_db
def test_empty_honeypot_logs_nothing(
    allauth_request_ctx, mock_site_context, legal_repo_mock, caplog
):
    form = SiteAwareSignupForm(data=_signup_data())

    with caplog.at_level(logging.WARNING, logger="freedom_ls.accounts.forms"):
        form.is_valid()

    assert not [r for r in caplog.records if r.name == "freedom_ls.accounts.forms"]


@pytest.mark.django_db
def test_signup_page_renders_honeypot_inside_hidden_wrapper(mock_site_context):
    """Regression: an off-screen input can still take focus, so autofill filled it."""
    body = Client().get(reverse("account_signup")).content.decode()

    match = re.search(
        rf"<div hidden>\s*(<input[^>]*name=\"{HONEYPOT_FIELD}\"[^>]*>)\s*</div>", body
    )
    assert match, "honeypot input is not inside a <div hidden> wrapper"
    assert 'type="text"' in match.group(1)
    assert "-9999px" not in match.group(1)
    assert body.count(f'name="{HONEYPOT_FIELD}"') == 1


@pytest.mark.django_db
def test_filled_honeypot_rerenders_signup_page_with_message_and_no_user(
    mock_site_context,
):
    response = Client().post(
        reverse("account_signup"), _signup_data(**{HONEYPOT_FIELD: BOT_VALUE})
    )

    assert response.status_code == 200
    assert "try typing your details in by hand" in response.content.decode()
    assert not User.objects.filter(email="honeypot@example.com").exists()


@pytest.mark.django_db
def test_signup_with_empty_honeypot_creates_user(mock_site_context):
    Client().post(reverse("account_signup"), _signup_data(**{HONEYPOT_FIELD: ""}))

    assert User.objects.filter(email="honeypot@example.com").exists()


class _HoneypotOnlyForm(forms.Form):
    first_name = forms.CharField(required=False)
    fax_number = honeypot_field()


def _cleaned_form(fax_number: str) -> _HoneypotOnlyForm:
    form = _HoneypotOnlyForm(data={"fax_number": fax_number})
    form.is_valid()
    return form


@pytest.mark.django_db
def test_reject_honeypot_adds_given_message_when_filled(allauth_request_ctx):
    form = _cleaned_form(BOT_VALUE)

    reject_honeypot(form, allauth_request_ctx, "Custom message")

    assert form.non_field_errors() == ["Custom message"]


@pytest.mark.django_db
def test_reject_honeypot_leaves_form_untouched_when_empty(allauth_request_ctx):
    form = _cleaned_form("")

    reject_honeypot(form, allauth_request_ctx, "Custom message")

    assert not form.errors


@pytest.mark.django_db
def test_apply_signup_name_policy_makes_first_name_optional(
    allauth_request_ctx, mock_site_context, site
):
    policy = SiteSignupPolicyFactory(site=site, require_name=False)
    form = _HoneypotOnlyForm()
    form.fields["first_name"].required = True

    apply_signup_name_policy(form, policy)

    assert form.fields["first_name"].required is False


@pytest.mark.django_db
def test_accepted_legal_docs_returns_only_the_ticked_documents(
    mock_site_context, legal_repo_mock
):
    accepted = accepted_legal_docs(
        mock_site_context, {"accept_terms": True, "accept_privacy": False}
    )

    assert [doc_type for doc_type, _doc in accepted] == ["terms"]
    assert accepted[0][1].version == "1.5"


@pytest.mark.django_db
def test_accepted_legal_docs_skips_a_ticked_document_that_does_not_resolve(
    mock_site_context, mock_legal_blobs
):
    accepted = accepted_legal_docs(
        mock_site_context, {"accept_terms": True, "accept_privacy": True}
    )

    assert accepted == []


def test_tripped_honeypot_is_true_when_the_field_holds_text():
    form = _cleaned_form(BOT_VALUE)

    assert tripped_honeypot(form) is True


def test_tripped_honeypot_is_false_when_the_field_is_empty():
    form = _cleaned_form("")

    assert tripped_honeypot(form) is False


def _picture_form(user, data: bytes) -> UserForm:
    return UserForm(
        {"first_name": user.first_name, "last_name": user.last_name},
        {"profile_picture": SimpleUploadedFile("me.jpg", data)},
        instance=user,
    )


@pytest.mark.django_db
def test_user_form_stores_a_400_square_webp_under_the_users_prefix(
    mock_site_context, pathless_profile_picture_storage
):
    user = UserFactory()
    form = _picture_form(user, jpeg_bytes())

    assert form.is_valid(), form.errors
    saved = form.save()

    with Image.open(io.BytesIO(saved.profile_picture.read())) as stored:
        assert (stored.format, stored.size) == ("WEBP", (400, 400))
    assert str(saved.profile_picture.name).startswith(f"profile_pictures/{user.pk}/")


@pytest.mark.django_db
def test_user_form_without_a_file_keeps_the_existing_picture(
    mock_site_context, pathless_profile_picture_storage
):
    user = UserFactory(with_profile_picture=True)
    stored_name = user.profile_picture.name
    form = UserForm({"first_name": "Renamed", "last_name": ""}, {}, instance=user)

    assert form.is_valid(), form.errors
    form.save()

    user.refresh_from_db()
    assert (user.first_name, user.profile_picture.name) == ("Renamed", stored_name)


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"not an image at all", WRONG_TYPE),
        (gif_bytes(), WRONG_TYPE),
        (truncated_jpeg_bytes(), UNREADABLE),
    ],
)
def test_user_form_puts_a_rejected_picture_on_the_field(
    mock_site_context, data: bytes, message: str
):
    form = _picture_form(UserFactory(), data)

    assert not form.is_valid()
    assert form.errors["profile_picture"] == [message]


@pytest.mark.django_db
def test_user_form_deletes_the_superseded_picture_on_commit_not_before(
    mock_site_context,
    pathless_profile_picture_storage,
    django_capture_on_commit_callbacks,
):
    user = UserFactory(with_profile_picture=True)
    old_name = user.profile_picture.name
    storage = user.profile_picture.storage
    form = _picture_form(user, jpeg_bytes())
    assert form.is_valid(), form.errors

    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        saved = form.save()
    still_there_before_commit = storage.exists(old_name)
    callbacks[0]()

    assert saved.profile_picture.name != old_name
    assert still_there_before_commit is True
    assert storage.exists(old_name) is False
    assert storage.exists(saved.profile_picture.name) is True


class _RollBackError(Exception):
    pass


def _save_then_roll_back(form: UserForm) -> None:
    with transaction.atomic():
        form.save()
        raise _RollBackError


@pytest.mark.django_db
def test_user_form_keeps_the_old_picture_when_the_save_rolls_back(
    mock_site_context,
    pathless_profile_picture_storage,
    django_capture_on_commit_callbacks,
):
    user = UserFactory(with_profile_picture=True)
    old_name = user.profile_picture.name
    storage = user.profile_picture.storage
    form = _picture_form(user, jpeg_bytes())
    assert form.is_valid(), form.errors

    with (
        django_capture_on_commit_callbacks(execute=True),
        pytest.raises(_RollBackError),
    ):
        _save_then_roll_back(form)

    assert storage.exists(old_name) is True
    assert User._base_manager.get(pk=user.pk).profile_picture.name == old_name


@pytest.mark.django_db
def test_user_form_saving_names_alone_deletes_nothing(
    mock_site_context,
    pathless_profile_picture_storage,
    django_capture_on_commit_callbacks,
):
    user = UserFactory(with_profile_picture=True)
    old_name = user.profile_picture.name
    storage = user.profile_picture.storage
    form = UserForm({"first_name": "Renamed", "last_name": ""}, {}, instance=user)
    assert form.is_valid(), form.errors

    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        form.save()

    assert callbacks == []
    assert storage.exists(old_name) is True


@pytest.mark.django_db
def test_user_form_save_without_commit_raises(mock_site_context):
    form = UserForm({"first_name": "A", "last_name": "B"}, {}, instance=UserFactory())
    assert form.is_valid(), form.errors

    with pytest.raises(ValueError, match="commit=False"):
        form.save(commit=False)
