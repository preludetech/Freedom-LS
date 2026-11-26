"""Every model a user force delete cascades into is either deletable from its
admin or on the list of models a force delete is allowed to take."""

from __future__ import annotations

import pytest

from django.contrib import admin
from django.db.models import CASCADE, Model
from django.test import RequestFactory

from freedom_ls.accounts import admin as accounts_admin
from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.learner_management.models import Learner
from freedom_ls.learner_progress.models import CourseProgress

pytestmark = pytest.mark.django_db


def _cascade_reach(roots: list[type[Model]]) -> set[type[Model]]:
    """Every model reached from the roots along CASCADE edges."""
    reached: set[type[Model]] = set()
    pending = list(roots)
    while pending:
        model = pending.pop()
        for relation in model._meta.related_objects:
            if relation.on_delete is not CASCADE:
                continue
            if relation.related_model not in reached:
                reached.add(relation.related_model)
                pending.append(relation.related_model)
    return reached


def _models_missing_from_the_allow_list(request: object) -> list[str]:
    reached = _cascade_reach([User, Learner, CourseProgress])
    return sorted(
        model._meta.label
        for model in reached
        if admin.site.is_registered(model)
        and not admin.site._registry[model].has_delete_permission(request)
        and model not in accounts_admin.USER_ERASURE_CASCADE_MODELS
    )


def test_every_refusing_model_a_user_force_delete_reaches_is_allowed(
    mock_site_context,
) -> None:
    request = RequestFactory().post("/")
    request.user = UserFactory(superuser=True)

    assert _models_missing_from_the_allow_list(request) == []
