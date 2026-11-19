"""The account area's sidebar: the pages an account holder moves between.

The entries cover pages of this app and of allauth, so the list is data here
rather than a panel-framework navigation group.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.http import HttpRequest
from django.urls import NoReverseMatch, reverse


@dataclass(frozen=True)
class SidebarEntry:
    label: str
    url_name: str
    #: Other URL names this entry is the current page for.
    also_current_for: tuple[str, ...] = ()
    #: Shown only when its URL resolves, for allauth apps a project may not enable.
    optional: bool = False


@dataclass(frozen=True)
class CurrentSidebarEntry:
    label: str
    url: str
    is_current: bool


SIDEBAR_ENTRIES: list[SidebarEntry] = [
    SidebarEntry("Personal details", "accounts:account_profile"),
    SidebarEntry("Email", "account_email"),
    SidebarEntry(
        "Password",
        "account_change_password",
        also_current_for=("account_set_password",),
    ),
    SidebarEntry("Account connections", "socialaccount_connections", optional=True),
    SidebarEntry("Two-factor authentication", "mfa_index", optional=True),
    SidebarEntry("Sessions", "usersessions_list", optional=True),
]


def sidebar_entries(request: HttpRequest) -> list[CurrentSidebarEntry]:
    """Each entry's URL and whether it is the page `request` is on, read from
    request.resolver_match.view_name. An optional entry whose URL does not
    reverse (NoReverseMatch) is left out."""
    match = request.resolver_match
    current_view = match.view_name if match is not None else ""
    entries: list[CurrentSidebarEntry] = []
    for entry in SIDEBAR_ENTRIES:
        try:
            url = reverse(entry.url_name)
        except NoReverseMatch:
            if entry.optional:
                continue
            raise
        entries.append(
            CurrentSidebarEntry(
                label=entry.label,
                url=url,
                is_current=current_view in (entry.url_name, *entry.also_current_for),
            )
        )
    return entries
