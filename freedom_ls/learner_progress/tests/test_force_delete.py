"""Force delete: what a plan collects, what blocks it, and the delete itself."""

from __future__ import annotations

import pytest

from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from django.http import HttpRequest
from django.test import RequestFactory

from freedom_ls.accounts import admin as accounts_admin
from freedom_ls.accounts.factories import LegalConsentFactory, UserFactory
from freedom_ls.accounts.models import LegalConsent, User
from freedom_ls.audit_log.models import AuditLogEntry
from freedom_ls.learner_progress.force_delete import (
    ForceDeleteBlockedError,
    build_plan,
    force_delete_users,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def actor() -> User:
    user: User = UserFactory(superuser=True)
    return user


@pytest.fixture
def request_for(actor: User) -> HttpRequest:
    request = RequestFactory().post("/")
    request.user = actor
    return request


def _plan(user: User, request: HttpRequest):
    return build_plan(
        targets=[user], progress_roots=[], request=request, admin_site=admin.site
    )


def test_plan_counts_each_model_once(mock_site_context, request_for) -> None:
    user: User = UserFactory()
    LegalConsentFactory(user=user)
    LegalConsentFactory(user=user, document_type="privacy")

    plan = _plan(user, request_for)

    assert plan.counts()["users"] == 1
    assert plan.counts()["legal consents"] == 2


def test_plan_can_run_for_a_user_whose_rows_are_all_allowed(
    mock_site_context, request_for
) -> None:
    user: User = UserFactory()
    LegalConsentFactory(user=user)

    plan = _plan(user, request_for)

    assert plan.can_run is True
    assert plan.blocking_models == ()


def test_plan_names_a_model_whose_admin_refuses_delete_and_is_not_allowed(
    mock_site_context, request_for, monkeypatch
) -> None:
    user: User = UserFactory()
    LegalConsentFactory(user=user)
    monkeypatch.setattr(accounts_admin, "USER_ERASURE_CASCADE_MODELS", set())

    plan = _plan(user, request_for)

    assert plan.can_run is False
    assert plan.blocking_models == ("legal consent",)


def test_force_delete_removes_the_user_and_their_rows(
    mock_site_context, request_for, actor
) -> None:
    user: User = UserFactory()
    LegalConsentFactory(user=user)

    count = force_delete_users(
        [user],
        actor=actor,
        reason="Erasure requested",
        request=request_for,
        admin_site=admin.site,
    )

    assert count == 1
    assert not User._base_manager.filter(pk=user.pk).exists()
    assert not LegalConsent._base_manager.filter(user_id=user.pk).exists()


def test_force_delete_writes_one_entry_that_outlives_the_user(
    mock_site_context, request_for, actor
) -> None:
    user: User = UserFactory(first_name="Ada", last_name="Lovelace")
    user_pk = user.pk

    force_delete_users(
        [user],
        actor=actor,
        reason="Erasure requested",
        request=request_for,
        admin_site=admin.site,
    )

    entry = AuditLogEntry.unscoped.get()
    assert entry.action == "user.deleted"
    assert entry.actor == actor
    assert entry.target_label == "Ada Lovelace"
    assert entry.target_object_id == str(user_pk)
    assert entry.target_content_type == ContentType.objects.get_for_model(User)
    assert entry.organisation is None
    assert entry.reason == "Erasure requested"
    assert entry.details["counts"]["users"] == 1


def test_force_delete_of_a_blocked_user_raises_and_deletes_nothing(
    mock_site_context, request_for, actor, monkeypatch
) -> None:
    user: User = UserFactory()
    LegalConsentFactory(user=user)
    monkeypatch.setattr(accounts_admin, "USER_ERASURE_CASCADE_MODELS", set())

    with pytest.raises(ForceDeleteBlockedError) as blocked:
        force_delete_users(
            [user],
            actor=actor,
            reason="Erasure requested",
            request=request_for,
            admin_site=admin.site,
        )

    assert blocked.value.blocking_models == ("legal consent",)
    assert User._base_manager.filter(pk=user.pk).exists()
    assert not AuditLogEntry.unscoped.exists()
