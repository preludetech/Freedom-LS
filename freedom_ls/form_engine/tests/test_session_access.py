"""Tests for form_engine.session_access."""

from __future__ import annotations

import pytest

from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.backends.db import SessionStore
from django.http import HttpRequest

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.form_engine.factories import FormProgressFactory
from freedom_ls.form_engine.session_access import (
    ANONYMOUS_FORM_PROGRESS_SESSION_KEY,
    allow_anonymous_form_progress,
    forget_all_anonymous_form_progress,
    owned_form_progress,
)


def _anonymous_request() -> HttpRequest:
    request = HttpRequest()
    request.user = AnonymousUser()
    request.session = SessionStore()
    return request


@pytest.mark.django_db
def test_a_signed_in_user_owns_their_own_sittings(mock_site_context):
    user = UserFactory()
    sitting = FormProgressFactory(user=user)
    FormProgressFactory(user=UserFactory())
    request = _anonymous_request()
    request.user = user

    assert list(owned_form_progress(request)) == [sitting]


@pytest.mark.django_db
def test_an_allowed_user_less_sitting_is_owned_by_the_session(mock_site_context):
    sitting = FormProgressFactory(user=None)
    request = _anonymous_request()
    allow_anonymous_form_progress(request, sitting)

    assert list(owned_form_progress(request)) == [sitting]


@pytest.mark.django_db
def test_a_user_less_sitting_nobody_allowed_is_not_owned(mock_site_context):
    FormProgressFactory(user=None)

    assert list(owned_form_progress(_anonymous_request())) == []


@pytest.mark.django_db
def test_an_allowed_sitting_that_gained_a_user_is_no_longer_owned(mock_site_context):
    sitting = FormProgressFactory(user=None)
    request = _anonymous_request()
    allow_anonymous_form_progress(request, sitting)
    sitting.user = UserFactory()
    sitting.save(update_fields=["user"])

    assert list(owned_form_progress(request)) == []


@pytest.mark.django_db
def test_allowing_a_sitting_twice_stores_it_once(mock_site_context):
    sitting = FormProgressFactory(user=None)
    request = _anonymous_request()

    allow_anonymous_form_progress(request, sitting)
    allow_anonymous_form_progress(request, sitting)

    assert request.session[ANONYMOUS_FORM_PROGRESS_SESSION_KEY] == [str(sitting.pk)]


@pytest.mark.django_db
def test_an_allowed_sitting_that_was_completed_is_no_longer_owned(mock_site_context):
    sitting = FormProgressFactory(user=None)
    request = _anonymous_request()
    allow_anonymous_form_progress(request, sitting)
    sitting.complete()

    assert list(owned_form_progress(request)) == []


@pytest.mark.django_db
def test_forgetting_all_sittings_leaves_the_session_owning_none(mock_site_context):
    request = _anonymous_request()
    allow_anonymous_form_progress(request, FormProgressFactory(user=None))
    allow_anonymous_form_progress(request, FormProgressFactory(user=None))

    forget_all_anonymous_form_progress(request)

    assert list(owned_form_progress(request)) == []
