"""The force delete confirmation page for users."""

from __future__ import annotations

import re
from collections.abc import Callable
from urllib.parse import parse_qs

import pytest

from django.contrib.auth.models import Permission
from django.contrib.sites.models import Site
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from freedom_ls.accounts import admin as accounts_admin
from freedom_ls.accounts.factories import LegalConsentFactory, UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.audit_log.models import REASON_LENGTH, AuditLogEntry
from freedom_ls.form_engine.models import FormProgress
from freedom_ls.learner_management.factories import LearnerFactory
from freedom_ls.learner_management.models import Learner
from freedom_ls.learner_progress import force_delete_admin
from freedom_ls.learner_progress.factories import (
    CourseFormAttemptFactory,
    CourseProgressFactory,
)
from freedom_ls.learner_progress.models import CourseFormAttempt, CourseProgress
from freedom_ls.learner_progress.tests.helpers import stub_unlinked
from freedom_ls.tests.factories import SiteFactory
from freedom_ls.tests.site_context import site_context

pytestmark = pytest.mark.django_db

FORCE_DELETE = "admin:freedom_ls_accounts_user_force_delete"


def _url(*users: User) -> str:
    ids = ",".join(str(user.pk) for user in users)
    return f"{reverse(FORCE_DELETE)}?ids={ids}"


@pytest.fixture
def staff_with_every_user_permission(
    mock_site_context: Site, logged_in_client: Callable[[User], Client]
) -> Client:
    user = UserFactory(staff=True)
    user.user_permissions.add(
        *Permission.objects.filter(
            content_type__app_label="freedom_ls_accounts",
            content_type__model="user",
        )
    )
    client: Client = logged_in_client(user)
    return client


def test_change_page_offers_force_delete_to_a_superuser(staff_client: Client) -> None:
    user = UserFactory()

    response = staff_client.get(
        reverse("admin:freedom_ls_accounts_user_change", args=[user.pk])
    )

    assert "Force delete" in response.content.decode()


def test_change_page_hides_force_delete_from_staff(
    staff_with_every_user_permission: Client,
) -> None:
    user = UserFactory()

    response = staff_with_every_user_permission.get(
        reverse("admin:freedom_ls_accounts_user_change", args=[user.pk])
    )

    assert response.status_code == 200
    assert "Force delete" not in response.content.decode()


def test_detail_action_redirects_to_the_confirmation_page(staff_client: Client) -> None:
    user = UserFactory()

    response = staff_client.get(
        reverse("admin:freedom_ls_accounts_user_force_delete_one", args=[user.pk])
    )

    assert response.status_code == 302
    assert response.url == _url(user)


@pytest.mark.parametrize("method", ["get", "post"])
def test_staff_without_superuser_get_403(
    staff_with_every_user_permission: Client, method: str
) -> None:
    user = UserFactory()

    response = getattr(staff_with_every_user_permission, method)(_url(user))

    assert response.status_code == 403


def test_page_links_deactivate_the_user_to_the_change_page(
    staff_client: Client,
) -> None:
    user = UserFactory()

    response = staff_client.get(_url(user))

    change_url = reverse("admin:freedom_ls_accounts_user_change", args=[user.pk])
    body = response.content.decode()
    assert "deactivate the user" in body
    assert f'href="{change_url}"' in body
    assert "SACAA" not in body


def test_page_counts_each_model_once(staff_client: Client) -> None:
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
    staff_client: Client, reason: str | None
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
    staff_client: Client, monkeypatch: pytest.MonkeyPatch
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


def test_blocked_post_deletes_nothing(
    staff_client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = UserFactory()
    LegalConsentFactory(user=user)
    monkeypatch.setattr(accounts_admin, "USER_ERASURE_CASCADE_MODELS", set())

    response = staff_client.post(_url(user), {"ids": str(user.pk), "reason": "Why"})

    assert response.status_code == 422
    assert User.objects.filter(pk=user.pk).exists()


def test_another_sites_user_is_a_404_on_get(staff_client: Client) -> None:
    with site_context(SiteFactory()):
        other = UserFactory()

    response = staff_client.get(_url(other))

    assert response.status_code == 404


def test_another_sites_user_is_a_404_on_post_and_survives(staff_client: Client) -> None:
    with site_context(SiteFactory()):
        other = UserFactory()

    response = staff_client.post(_url(other), {"ids": str(other.pk), "reason": "Why"})

    assert response.status_code == 404
    assert User._base_manager.filter(pk=other.pk).exists()


def test_malformed_id_is_a_404(staff_client: Client) -> None:
    response = staff_client.get(f"{reverse(FORCE_DELETE)}?ids=not-a-number")

    assert response.status_code == 404


def test_post_deletes_the_user_and_records_the_reason(staff_client: Client) -> None:
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


def test_page_lists_each_model_in_a_labelled_scrollable_region(
    staff_client: Client,
) -> None:
    user = UserFactory()
    LegalConsentFactory(user=user)

    response = staff_client.get(_url(user))

    body = response.content.decode()
    assert 'aria-label="Legal consents"' in body
    assert 'role="region"' in body
    assert 'data-icon="dropdown"' in body


def test_changelist_action_redirects_to_the_confirmation_page_with_the_ids(
    staff_client: Client,
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


def test_changelist_offers_force_delete_and_export_to_a_superuser(
    staff_client: Client,
) -> None:
    response = staff_client.get(reverse("admin:freedom_ls_accounts_user_changelist"))

    body = response.content.decode()
    assert "Force delete selected users" in body
    assert "export_admin_action" in body


def test_changelist_hides_force_delete_from_staff(
    staff_with_every_user_permission: Client,
) -> None:
    response = staff_with_every_user_permission.get(
        reverse("admin:freedom_ls_accounts_user_changelist")
    )

    assert response.status_code == 200
    assert "Force delete selected users" not in response.content.decode()


def test_cancel_returns_to_the_change_page_for_one_user(staff_client: Client) -> None:
    user = UserFactory()

    response = staff_client.get(_url(user))

    assert response.context["cancel_url"] == reverse(
        "admin:freedom_ls_accounts_user_change", args=[user.pk]
    )


def test_cancel_returns_to_the_changelist_for_several_users(
    staff_client: Client,
) -> None:
    first, second = UserFactory(), UserFactory()

    response = staff_client.get(_url(first, second))

    assert response.context["cancel_url"] == reverse(
        "admin:freedom_ls_accounts_user_changelist"
    )


def test_several_users_each_get_an_entry_with_the_same_reason(
    staff_client: Client,
) -> None:
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


def test_another_superuser_can_be_force_deleted(staff_client: Client) -> None:
    other = UserFactory(superuser=True)

    response = staff_client.post(
        _url(other), {"ids": str(other.pk), "reason": "Left the team"}
    )

    assert response.status_code == 302
    assert not User._base_manager.filter(pk=other.pk).exists()


def test_page_warns_in_the_second_person_only_when_the_actor_is_a_target(
    mock_site_context: Site, logged_in_client: Callable[[User], Client]
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
    mock_site_context: Site, logged_in_client: Callable[[User], Client]
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
    staff_client: Client,
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


def test_page_lists_unlinked_rows_with_their_count(
    staff_client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = UserFactory()
    calls = stub_unlinked(monkeypatch, 4)

    response = staff_client.get(_url(user))

    body = response.content.decode()
    assert calls[0] == [user]
    assert "Also erased, found by email address" in body
    assert "Learners (4)" in body


def test_page_does_not_list_an_unlinked_model_with_a_zero_count(
    staff_client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = UserFactory()
    stub_unlinked(monkeypatch, 0)

    response = staff_client.get(_url(user))

    assert "found by email address" not in response.content.decode()


def test_post_records_the_unlinked_counts_in_the_entry(
    staff_client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = UserFactory()
    stub_unlinked(monkeypatch, 4)

    staff_client.post(_url(user), {"ids": str(user.pk), "reason": "Why"})

    assert AuditLogEntry.unscoped.get().details["unlinked"] == {"learners": 4}


LEARNER_FORCE_DELETE = "admin:freedom_ls_learner_management_learner_force_delete"


def _learner_url(*learners: Learner) -> str:
    ids = ",".join(str(learner.pk) for learner in learners)
    return f"{reverse(LEARNER_FORCE_DELETE)}?ids={ids}"


@pytest.fixture
def staff_with_every_learner_permission(
    mock_site_context: Site, logged_in_client: Callable[[User], Client]
) -> Client:
    user = UserFactory(staff=True)
    user.user_permissions.add(
        *Permission.objects.filter(
            content_type__app_label="freedom_ls_learner_management",
            content_type__model="learner",
        )
    )
    client: Client = logged_in_client(user)
    return client


def test_learner_page_wording_and_links(staff_client: Client) -> None:
    learner = LearnerFactory()

    response = staff_client.get(_learner_url(learner))

    learner_page = reverse(
        "educator_interface:interface",
        kwargs={
            "organisation_slug": learner.organisation.slug,
            "path_string": f"learners/{learner.pk}",
        },
    )
    body = response.content.decode()
    assert response.status_code == 200
    assert "deactivate the learner" in body
    assert f'href="{learner_page}"' in body
    assert "their user account can still sign in" in body
    assert "SACAA" not in body
    assert (
        "The user account and their learner records in other organisations stay."
        in body
    )
    assert "recorded against every selected learner" in body


def test_learner_page_counts_the_learners_course_progress(staff_client: Client) -> None:
    learner = LearnerFactory()
    CourseProgressFactory(learner=learner)

    response = staff_client.get(_learner_url(learner))

    counts = response.context["plan"].counts()
    assert counts[str(CourseProgress._meta.verbose_name_plural)] == 1
    assert counts[str(Learner._meta.verbose_name_plural)] == 1


@pytest.mark.parametrize("method", ["get", "post"])
def test_staff_without_superuser_get_403_on_the_learner_view(
    staff_with_every_learner_permission: Client, method: str
) -> None:
    learner = LearnerFactory()

    response = getattr(staff_with_every_learner_permission, method)(
        _learner_url(learner)
    )

    assert response.status_code == 403


def test_another_sites_learner_is_a_404_and_survives(staff_client: Client) -> None:
    with site_context(SiteFactory()):
        other = LearnerFactory()

    response = staff_client.post(
        _learner_url(other), {"ids": str(other.pk), "reason": "Why"}
    )

    assert response.status_code == 404
    assert Learner._base_manager.filter(pk=other.pk).exists()


def test_learner_post_removes_the_learner_and_keeps_the_user(
    staff_client: Client,
) -> None:
    learner = LearnerFactory()
    other = LearnerFactory(user=learner.user)

    response = staff_client.post(
        _learner_url(learner), {"ids": str(learner.pk), "reason": "Left"}
    )

    entry = AuditLogEntry.unscoped.get()
    assert response.status_code == 302
    assert response.url == reverse(
        "admin:freedom_ls_learner_management_learner_changelist"
    )
    assert not Learner._base_manager.filter(pk=learner.pk).exists()
    assert Learner._base_manager.filter(pk=other.pk).exists()
    assert User.objects.filter(pk=learner.user_id).exists()
    assert entry.action == "learner.removed"
    assert entry.reason == "Left"
    assert entry.organisation_id == learner.organisation_id


def test_learner_cancel_returns_to_the_change_page(staff_client: Client) -> None:
    learner = LearnerFactory()

    response = staff_client.get(_learner_url(learner))

    assert response.context["cancel_url"] == reverse(
        "admin:freedom_ls_learner_management_learner_change", args=[learner.pk]
    )


def test_learner_invalid_reason_is_422_and_deletes_nothing(
    staff_client: Client,
) -> None:
    learner = LearnerFactory()

    response = staff_client.post(
        _learner_url(learner), {"ids": str(learner.pk), "reason": " "}
    )

    assert response.status_code == 422
    assert Learner._base_manager.filter(pk=learner.pk).exists()


def test_reason_label_is_a_block_so_it_sits_above_the_textarea(
    staff_client: Client,
) -> None:
    """The Reason label sat inline beside the textarea at desktop width."""
    user = UserFactory()

    response = staff_client.get(_url(user))

    body = response.content.decode()
    label = re.search(r'<label for="id_reason"[^>]*>', body)
    assert label is not None
    classes = re.search(r'class="([^"]*)"', label.group(0))
    assert classes is not None
    assert "block" in classes.group(1).split()


def test_model_rows_read_in_sentence_case_and_sort_regardless_of_case(
    staff_client: Client,
) -> None:
    """Rows used to show the raw lower case model name and sort capitals first."""
    user = UserFactory()
    LegalConsentFactory(user=user)
    CourseFormAttemptFactory(
        course_progress__learner=LearnerFactory(user=user),
    )

    body = staff_client.get(_url(user)).content.decode()

    assert "Users (1)" in body
    assert "Legal consents (1)" in body
    assert "users (1)" not in body
    names = re.findall(r"<span>([^<(]+) \(\d+\)</span>", body)
    assert names == sorted(names, key=str.casefold)
    assert "Form progress records" in names


def test_learner_page_queries_do_not_grow_with_the_selection(
    staff_client: Client,
) -> None:
    one = [LearnerFactory()]
    five = [LearnerFactory() for _ in range(5)]

    with CaptureQueriesContext(connection) as for_one:
        staff_client.get(_learner_url(*one))
    with CaptureQueriesContext(connection) as for_five:
        staff_client.get(_learner_url(*five))

    assert len(for_five) == len(for_one)


def test_changelist_action_refuses_a_selection_over_the_cap(
    staff_client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(force_delete_admin, "FORCE_DELETE_MAX_SELECTION", 2)
    users = [UserFactory() for _ in range(3)]

    response = staff_client.post(
        reverse("admin:freedom_ls_accounts_user_changelist"),
        {
            "action": "force_delete_selected",
            "_selected_action": [user.pk for user in users],
        },
        follow=True,
    )

    assert response.redirect_chain[-1][0] == reverse(
        "admin:freedom_ls_accounts_user_changelist"
    )
    assert "Select at most 2 users to force delete at once." in (
        response.content.decode()
    )
