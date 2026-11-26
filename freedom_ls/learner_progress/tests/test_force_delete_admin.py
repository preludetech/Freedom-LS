"""The force delete confirmation page for users."""

from __future__ import annotations

from urllib.parse import parse_qs

import pytest

from django.contrib.auth.models import Permission
from django.test import Client
from django.urls import reverse

from freedom_ls.accounts import admin as accounts_admin
from freedom_ls.accounts.factories import LegalConsentFactory, UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.audit_log.models import REASON_LENGTH, AuditLogEntry
from freedom_ls.form_engine.models import FormProgress
from freedom_ls.learner_progress.factories import CourseFormAttemptFactory
from freedom_ls.learner_progress.models import CourseFormAttempt
from freedom_ls.tests.factories import SiteFactory
from freedom_ls.tests.site_context import site_context

pytestmark = pytest.mark.django_db

FORCE_DELETE = "admin:freedom_ls_accounts_user_force_delete"


def _url(*users: User) -> str:
    ids = ",".join(str(user.pk) for user in users)
    return f"{reverse(FORCE_DELETE)}?ids={ids}"


@pytest.fixture
def staff_with_every_user_permission(mock_site_context, logged_in_client) -> Client:
    user = UserFactory(staff=True)
    user.user_permissions.add(
        *Permission.objects.filter(
            content_type__app_label="freedom_ls_accounts",
            content_type__model="user",
        )
    )
    client: Client = logged_in_client(user)
    return client


def test_change_page_offers_force_delete_to_a_superuser(staff_client) -> None:
    user = UserFactory()

    response = staff_client.get(
        reverse("admin:freedom_ls_accounts_user_change", args=[user.pk])
    )

    assert "Force delete" in response.content.decode()


def test_change_page_hides_force_delete_from_staff(
    staff_with_every_user_permission,
) -> None:
    user = UserFactory()

    response = staff_with_every_user_permission.get(
        reverse("admin:freedom_ls_accounts_user_change", args=[user.pk])
    )

    assert response.status_code == 200
    assert "Force delete" not in response.content.decode()


def test_detail_action_redirects_to_the_confirmation_page(staff_client) -> None:
    user = UserFactory()

    response = staff_client.get(
        reverse("admin:freedom_ls_accounts_user_force_delete_one", args=[user.pk])
    )

    assert response.status_code == 302
    assert response.url == _url(user)


@pytest.mark.parametrize("method", ["get", "post"])
def test_staff_without_superuser_get_403(
    staff_with_every_user_permission, method: str
) -> None:
    user = UserFactory()

    response = getattr(staff_with_every_user_permission, method)(_url(user))

    assert response.status_code == 403


def test_page_links_deactivate_the_user_to_the_change_page(staff_client) -> None:
    user = UserFactory()

    response = staff_client.get(_url(user))

    change_url = reverse("admin:freedom_ls_accounts_user_change", args=[user.pk])
    body = response.content.decode()
    assert "deactivate the user" in body
    assert f'href="{change_url}"' in body


def test_page_counts_each_model_once(staff_client) -> None:
    user = UserFactory()
    LegalConsentFactory(user=user)
    LegalConsentFactory(user=user, document_type="privacy")

    response = staff_client.get(_url(user))

    plan = response.context["plan"]
    assert plan.counts()["legal consents"] == 2
    assert plan.counts()["users"] == 1


@pytest.mark.parametrize(
    "reason", [None, "   ", "x" * (REASON_LENGTH + 1)], ids=["missing", "blank", "long"]
)
def test_invalid_reason_rerenders_with_422_and_deletes_nothing(
    staff_client, reason: str | None
) -> None:
    user = UserFactory()
    data = {"ids": str(user.pk)}
    if reason is not None:
        data["reason"] = reason

    response = staff_client.post(_url(user), data)

    assert response.status_code == 422
    assert "reason" in response.context["form"].errors
    assert User.objects.filter(pk=user.pk).exists()


def test_blocking_model_is_named_and_no_form_is_offered(
    staff_client, monkeypatch
) -> None:
    user = UserFactory()
    LegalConsentFactory(user=user)
    monkeypatch.setattr(accounts_admin, "USER_ERASURE_CASCADE_MODELS", set())

    response = staff_client.get(_url(user))

    body = response.content.decode()
    assert "legal consent" in response.context["plan"].blocking_models
    assert "legal consent" in body
    assert "cannot run" in body
    assert 'name="reason"' not in body


def test_blocked_post_deletes_nothing(staff_client, monkeypatch) -> None:
    user = UserFactory()
    LegalConsentFactory(user=user)
    monkeypatch.setattr(accounts_admin, "USER_ERASURE_CASCADE_MODELS", set())

    response = staff_client.post(_url(user), {"ids": str(user.pk), "reason": "Why"})

    assert response.status_code == 422
    assert User.objects.filter(pk=user.pk).exists()


def test_another_sites_user_is_a_404_on_get(staff_client) -> None:
    with site_context(SiteFactory()):
        other = UserFactory()

    response = staff_client.get(_url(other))

    assert response.status_code == 404


def test_another_sites_user_is_a_404_on_post_and_survives(staff_client) -> None:
    with site_context(SiteFactory()):
        other = UserFactory()

    response = staff_client.post(_url(other), {"ids": str(other.pk), "reason": "Why"})

    assert response.status_code == 404
    assert User._base_manager.filter(pk=other.pk).exists()


def test_malformed_id_is_a_404(staff_client) -> None:
    response = staff_client.get(f"{reverse(FORCE_DELETE)}?ids=not-a-number")

    assert response.status_code == 404


def test_post_deletes_the_user_and_records_the_reason(staff_client) -> None:
    user = UserFactory()
    user_pk = user.pk

    response = staff_client.post(
        _url(user), {"ids": str(user.pk), "reason": "Erasure requested"}
    )

    entry = AuditLogEntry.unscoped.get()
    assert response.status_code == 302
    assert response.url == reverse("admin:freedom_ls_accounts_user_changelist")
    assert not User._base_manager.filter(pk=user_pk).exists()
    assert entry.action == "user.deleted"
    assert entry.reason == "Erasure requested"
    assert entry.organisation is None


def test_page_lists_each_model_in_a_labelled_scrollable_region(staff_client) -> None:
    user = UserFactory()
    LegalConsentFactory(user=user)

    response = staff_client.get(_url(user))

    body = response.content.decode()
    assert 'aria-label="legal consents"' in body
    assert 'role="region"' in body
    assert 'data-icon="dropdown"' in body


def test_changelist_action_redirects_to_the_confirmation_page_with_the_ids(
    staff_client,
) -> None:
    first, second = UserFactory(), UserFactory()

    response = staff_client.post(
        reverse("admin:freedom_ls_accounts_user_changelist"),
        {
            "action": "force_delete_selected",
            "_selected_action": [first.pk, second.pk],
        },
    )

    assert response.status_code == 302
    path, query = response.url.split("?")
    assert path == reverse(FORCE_DELETE)
    assert set(parse_qs(query)["ids"][0].split(",")) == {str(first.pk), str(second.pk)}


def test_changelist_offers_force_delete_and_export_to_a_superuser(staff_client) -> None:
    response = staff_client.get(reverse("admin:freedom_ls_accounts_user_changelist"))

    body = response.content.decode()
    assert "Force delete selected users" in body
    assert "export_admin_action" in body


def test_changelist_hides_force_delete_from_staff(
    staff_with_every_user_permission,
) -> None:
    response = staff_with_every_user_permission.get(
        reverse("admin:freedom_ls_accounts_user_changelist")
    )

    assert response.status_code == 200
    assert "Force delete selected users" not in response.content.decode()


def test_cancel_returns_to_the_change_page_for_one_user(staff_client) -> None:
    user = UserFactory()

    response = staff_client.get(_url(user))

    assert response.context["cancel_url"] == reverse(
        "admin:freedom_ls_accounts_user_change", args=[user.pk]
    )


def test_cancel_returns_to_the_changelist_for_several_users(staff_client) -> None:
    first, second = UserFactory(), UserFactory()

    response = staff_client.get(_url(first, second))

    assert response.context["cancel_url"] == reverse(
        "admin:freedom_ls_accounts_user_changelist"
    )


def test_several_users_each_get_an_entry_with_the_same_reason(staff_client) -> None:
    first, second = UserFactory(), UserFactory()

    response = staff_client.post(
        _url(first, second),
        {"ids": f"{first.pk},{second.pk}", "reason": "Erasure requested"},
    )

    entries = AuditLogEntry.unscoped.filter(action="user.deleted")
    assert response.status_code == 302
    assert entries.count() == 2
    assert set(entries.values_list("reason", flat=True)) == {"Erasure requested"}
    assert not User._base_manager.filter(pk__in=[first.pk, second.pk]).exists()


def test_another_superuser_can_be_force_deleted(staff_client) -> None:
    other = UserFactory(superuser=True)

    response = staff_client.post(
        _url(other), {"ids": str(other.pk), "reason": "Left the team"}
    )

    assert response.status_code == 302
    assert not User._base_manager.filter(pk=other.pk).exists()


def test_page_warns_in_the_second_person_only_when_the_actor_is_a_target(
    mock_site_context, logged_in_client
) -> None:
    actor = UserFactory(superuser=True)
    other = UserFactory()
    client = logged_in_client(actor)
    sentence = "Your own account is among them. You are signed out when it goes."

    own = client.get(_url(actor, other))
    others = client.get(_url(other))

    assert own.context["acting_on_self"] is True
    assert sentence in own.content.decode()
    assert others.context["acting_on_self"] is False
    assert sentence not in others.content.decode()


def test_a_superuser_force_deleting_their_own_account_gets_a_redirect(
    mock_site_context, logged_in_client
) -> None:
    actor = UserFactory(superuser=True)
    client = logged_in_client(actor)

    response = client.post(_url(actor), {"ids": str(actor.pk), "reason": "Leaving"})

    entry = AuditLogEntry.unscoped.get(action="user.deleted")
    assert response.status_code == 302
    assert response.url == reverse("admin:freedom_ls_accounts_user_changelist")
    assert not User._base_manager.filter(pk=actor.pk).exists()
    assert entry.actor_label == actor.display_name


def test_page_counts_a_course_form_attempt_once_and_post_deletes_it(
    staff_client,
) -> None:
    attempt = CourseFormAttemptFactory()
    user = attempt.course_progress.learner.user

    page = staff_client.get(_url(user))
    response = staff_client.post(_url(user), {"ids": str(user.pk), "reason": "Asked"})

    counts = page.context["plan"].counts()
    assert counts[str(CourseFormAttempt._meta.verbose_name_plural)] == 1
    assert counts[str(FormProgress._meta.verbose_name_plural)] == 1
    assert response.status_code == 302
    assert not CourseFormAttempt._base_manager.filter(pk=attempt.pk).exists()
    assert not User.objects.filter(pk=user.pk).exists()
