"""A browser's claim on a sitting no account owns yet is its session, and only that."""

from __future__ import annotations

import pytest

from django.http import Http404

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.form_engine.anonymous_sittings import (
    ANONYMOUS_SITTINGS_SESSION_KEY,
    forget_anonymous_sitting,
    remember_anonymous_sitting,
    sitting_for_request,
)
from freedom_ls.form_engine.factories import FormProgressFactory


def _request(rf, *, user=None, held=()):
    request = rf.get("/")
    request.session = {ANONYMOUS_SITTINGS_SESSION_KEY: [str(pk) for pk in held]}
    request.user = user if user is not None else _Anonymous()
    return request


class _Anonymous:
    is_authenticated = False


@pytest.mark.django_db
def test_remember_stores_the_pk_as_a_string(rf, mock_site_context):
    sitting = FormProgressFactory(user=None)
    request = _request(rf)

    remember_anonymous_sitting(request, sitting)

    assert request.session[ANONYMOUS_SITTINGS_SESSION_KEY] == [str(sitting.pk)]


@pytest.mark.django_db
def test_remember_reassigns_the_list(rf, mock_site_context):
    sitting = FormProgressFactory(user=None)
    request = _request(rf)
    before = request.session[ANONYMOUS_SITTINGS_SESSION_KEY]

    remember_anonymous_sitting(request, sitting)

    assert request.session[ANONYMOUS_SITTINGS_SESSION_KEY] is not before
    assert before == []


def test_forget_is_a_no_op_for_an_unknown_id(rf):
    request = _request(rf, held=["a"])

    forget_anonymous_sitting(request, "b")

    assert request.session[ANONYMOUS_SITTINGS_SESSION_KEY] == ["a"]


@pytest.mark.django_db
def test_sitting_for_request_returns_the_own_sitting(rf, mock_site_context):
    user = UserFactory()
    sitting = FormProgressFactory(user=user)

    found = sitting_for_request(_request(rf, user=user), str(sitting.pk))

    assert found == sitting


@pytest.mark.django_db
def test_sitting_for_request_returns_a_held_unowned_sitting(rf, mock_site_context):
    sitting = FormProgressFactory(user=None)

    found = sitting_for_request(_request(rf, held=[sitting.pk]), str(sitting.pk))

    assert found == sitting


@pytest.mark.django_db
def test_sitting_for_request_is_404_for_a_held_id_that_is_now_owned(
    rf, mock_site_context
):
    sitting = FormProgressFactory(user=UserFactory())

    with pytest.raises(Http404):
        sitting_for_request(_request(rf, held=[sitting.pk]), str(sitting.pk))


@pytest.mark.django_db
def test_sitting_for_request_is_404_for_an_unheld_unowned_sitting(
    rf, mock_site_context
):
    sitting = FormProgressFactory(user=None)

    with pytest.raises(Http404):
        sitting_for_request(_request(rf), str(sitting.pk))
