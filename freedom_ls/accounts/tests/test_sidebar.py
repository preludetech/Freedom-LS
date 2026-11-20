"""Tests for the account area's sidebar entries."""

from __future__ import annotations

import pytest

from django.http import HttpRequest
from django.test import RequestFactory
from django.urls import NoReverseMatch, ResolverMatch

from freedom_ls.accounts import sidebar
from freedom_ls.accounts.sidebar import (
    CurrentSidebarEntry,
    SidebarEntry,
    sidebar_entries,
)


def _request_on(rf: RequestFactory, view_name: str) -> HttpRequest:
    request = rf.get("/")
    *namespaces, url_name = view_name.split(":")
    request.resolver_match = ResolverMatch(
        lambda request: None,
        (),
        {},
        url_name=url_name,
        app_names=namespaces,
        namespaces=namespaces,
    )
    return request


def test_personal_details_is_the_first_and_only_required_entry(rf):
    labels = [
        entry.label
        for entry in sidebar_entries(_request_on(rf, "accounts:account_profile"))
    ]

    # Email and Password are panels on Personal details, not entries; the rest
    # are allauth's optional pages, absent unless their apps are installed.
    assert labels == ["Personal details"]


def test_the_entry_for_the_page_is_current(rf):
    entries = sidebar_entries(_request_on(rf, "accounts:account_profile"))

    assert [e.label for e in entries if e.is_current] == ["Personal details"]


def test_an_entry_carries_its_url(rf):
    (entry,) = sidebar_entries(_request_on(rf, "accounts:account_profile"))

    assert entry.url == "/accounts/profile/"


def test_an_entry_is_current_for_its_other_url_names(rf, monkeypatch):
    monkeypatch.setattr(
        sidebar,
        "SIDEBAR_ENTRIES",
        [SidebarEntry("Log in", "account_login", also_current_for=("account_signup",))],
    )

    (entry,) = sidebar_entries(_request_on(rf, "account_signup"))

    assert entry.is_current


def test_an_optional_entry_whose_url_does_not_reverse_is_left_out(rf, monkeypatch):
    monkeypatch.setattr(
        sidebar,
        "SIDEBAR_ENTRIES",
        [
            SidebarEntry("Email", "account_email"),
            SidebarEntry("Missing", "no_such_url_name", optional=True),
        ],
    )

    labels = [e.label for e in sidebar_entries(_request_on(rf, "account_email"))]

    assert labels == ["Email"]


def test_a_required_entry_whose_url_does_not_reverse_raises(rf, monkeypatch):
    monkeypatch.setattr(
        sidebar, "SIDEBAR_ENTRIES", [SidebarEntry("Missing", "no_such_url_name")]
    )

    with pytest.raises(NoReverseMatch):
        sidebar_entries(_request_on(rf, "account_email"))


def test_an_added_entry_comes_back_with_its_url_and_current_state(rf, monkeypatch):
    monkeypatch.setattr(
        sidebar,
        "SIDEBAR_ENTRIES",
        [*sidebar.SIDEBAR_ENTRIES, SidebarEntry("Log in", "account_login")],
    )

    entries = sidebar_entries(_request_on(rf, "account_login"))

    assert entries[-1] == CurrentSidebarEntry("Log in", "/accounts/login/", True)
