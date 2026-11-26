"""Tests for the note that stands in for question detail a viewer may not see."""

from __future__ import annotations

from typing import cast

import pytest

from django.http import HttpRequest
from django.test import RequestFactory

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.educator_interface.panels.common.question_detail import (
    QUESTION_DETAIL_HIDDEN_NOTE,
    QUESTION_DETAIL_NEEDS_JAVASCRIPT_NOTE,
    question_detail_withheld_note,
)
from freedom_ls.educator_interface.tests.helpers import _grant
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation

pytestmark = pytest.mark.usefixtures("mock_site_context")


def _request(user: User, *, htmx: bool) -> HttpRequest:
    extra = {"HTTP_HX_REQUEST": "true"} if htmx else {}
    request = RequestFactory().get("/", **extra)
    request.user = user
    return request


def _organisation_with_user(*, holds_permission: bool) -> tuple[Organisation, User]:
    organisation = cast(Organisation, OrganisationFactory())
    user = cast(User, UserFactory(staff=True))
    _grant(user, "organisation_admin", organisation)
    if holds_permission:
        _grant(user, "question_bank_viewer", organisation)
    return organisation, user


@pytest.mark.django_db
def test_a_holder_on_an_htmx_request_gets_no_note() -> None:
    organisation, user = _organisation_with_user(holds_permission=True)

    note = question_detail_withheld_note(_request(user, htmx=True), organisation)

    assert note == ""


@pytest.mark.django_db
def test_a_holder_on_a_plain_request_is_told_to_turn_javascript_on() -> None:
    organisation, user = _organisation_with_user(holds_permission=True)

    note = question_detail_withheld_note(_request(user, htmx=False), organisation)

    assert note == QUESTION_DETAIL_NEEDS_JAVASCRIPT_NOTE


@pytest.mark.django_db
def test_a_non_holder_on_an_htmx_request_gets_the_hidden_note() -> None:
    organisation, user = _organisation_with_user(holds_permission=False)

    note = question_detail_withheld_note(_request(user, htmx=True), organisation)

    assert note == QUESTION_DETAIL_HIDDEN_NOTE


@pytest.mark.django_db
def test_a_non_holder_on_a_plain_request_gets_the_hidden_note_not_the_javascript_one() -> (
    None
):
    organisation, user = _organisation_with_user(holds_permission=False)

    note = question_detail_withheld_note(_request(user, htmx=False), organisation)

    assert note == QUESTION_DETAIL_HIDDEN_NOTE
