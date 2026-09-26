"""One-shot session events for every platform app.

An analytics event is a funnel moment that happens inside a view, not a page
render. A view records an event the moment the underlying thing happens; the
next render that reaches `partials/analytics_events.html` pops it and hands it
to every installed platform app (GA4, Meta, TikTok) to emit in its own shape.

Event names describe funnel moments every course access backend shares.
Whatever varies by backend travels as a parameter value, so a new backend adds
a value and leaves the event names, and any funnel built on them, alone.

This module is also the entry point for concrete projects. A downstream view
records its own events here, e.g. `generate_lead` from a marketing contact
form, with `lead_form` naming the form. Never pass anything a visitor typed.
"""

import re
from collections.abc import Mapping
from enum import StrEnum
from typing import NamedTuple, TypedDict, cast

from django.apps import apps
from django.http import HttpRequest

from freedom_ls.base.config import config

ANALYTICS_EVENTS_SESSION_KEY = "google_analytics_events"

# The apps that pop the queue. A project with none of them installed has no
# context processor to pop it, so recording would only grow the session.
PLATFORM_APPS = (
    "freedom_ls.google_tag",
    "freedom_ls.meta_pixel",
    "freedom_ls.tiktok_pixel",
)

# GA4's limits, the strictest of the three platforms. A name outside them is
# dropped by GA without an error anywhere, so it is refused here, where the
# developer will see it.
_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,39}$")
_RESERVED_PREFIXES = ("ga_", "google_", "firebase_")
_RESERVED_PARAMETER_NAMES = frozenset(
    {"user_id", "session_id", "currency", "uid", "cid", "customer_id"}
)
_MAX_VALUE_LENGTH = 100

_COUNTRY_CODE = re.compile(r"^[A-Z]{2}$")
# Cloudflare sends "XX" for an unknown country. Its "T1" (Tor) already fails
# the two-letter pattern.
_UNKNOWN_COUNTRY_CODES = frozenset({"XX"})


class AnalyticsEvent(StrEnum):
    SIGN_UP = "sign_up"
    COURSE_ACCESS_REQUESTED = "course_access_requested"
    COURSE_REGISTERED = "course_registered"
    COURSE_STARTED = "course_started"
    COURSE_COMPLETED = "course_completed"
    # FLS ships no lead form; the name is here for concrete projects to use.
    GENERATE_LEAD = "generate_lead"


class AnalyticsEventPayload(TypedDict):
    name: str
    params: dict[str, str]


# Google's EU user consent policy covers visitors in the EEA, the UK and
# Switzerland. It is also the set the country gate refuses: the Meta and
# TikTok pixels do not load for a visitor from one of these countries. FLS
# ships no consent banner, so the GA4 snippet denies all storage for these
# regions by default and GA4 and Ads send cookieless pings there. A
# downstream banner grants consent with gtag('consent', 'update', ...).
EU_CONSENT_POLICY_COUNTRIES = (
    # EU member states
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU",
    "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES",
    "SE",
    # The rest of the EEA
    "IS", "LI", "NO",
    # Outside the EEA, but covered by the same policy
    "GB", "CH",
)  # fmt: skip


def _is_valid_name(name: str) -> bool:
    return bool(_NAME_PATTERN.match(name)) and not name.startswith(_RESERVED_PREFIXES)


def record_analytics_event(
    request: HttpRequest, name: str, params: dict[str, str] | None = None
) -> None:
    """Record a one-shot event; the next page render emits it to every platform.

    `name` is a plain `str` so a concrete project can record events FLS has
    never heard of. Raises ValueError for an event or parameter name GA4 would
    reject. Values longer than GA4 accepts are cut to fit.
    """
    if not _is_valid_name(name):
        raise ValueError(f"Invalid GA4 event name: {name!r}")
    if not any(apps.is_installed(app) for app in PLATFORM_APPS):
        return
    params = params or {}
    for param_name in params:
        if not _is_valid_name(param_name) or param_name in _RESERVED_PARAMETER_NAMES:
            raise ValueError(f"Invalid GA4 parameter name: {param_name!r}")

    event: AnalyticsEventPayload = {
        "name": str(name),
        "params": {key: value[:_MAX_VALUE_LENGTH] for key, value in params.items()},
    }
    events = request.session.get(ANALYTICS_EVENTS_SESSION_KEY, [])
    # The whole payload is compared, so the same event for two courses in one
    # session reports both.
    if event not in events:
        # A new list, not an in-place append, so the session middleware's
        # dirty check (identity/equality on the stored value) sees the change.
        request.session[ANALYTICS_EVENTS_SESSION_KEY] = [*events, event]


def record_sign_up(request: HttpRequest, method: str = "email") -> None:
    # Social login would send its provider name as the method instead.
    record_analytics_event(request, AnalyticsEvent.SIGN_UP, {"method": method})


def pop_analytics_events(
    request: HttpRequest,
) -> list[AnalyticsEventPayload]:
    # The context processor calls this for every template render, including
    # ones built from a bare request that never passed through
    # SessionMiddleware (a template unit test rendering _base.html directly).
    # Such a request carries no events, so there is nothing to pop.
    session = getattr(request, "session", None)
    if session is None:
        return []
    return cast(
        list[AnalyticsEventPayload],
        session.pop(ANALYTICS_EVENTS_SESSION_KEY, []),
    )


def visitor_country(request: HttpRequest) -> str | None:
    """The visitor's country from the proxy header, or None when unknown."""
    header_name = config.VISITOR_COUNTRY_HEADER
    if not header_name:
        return None
    value = str(request.headers.get(header_name, "")).strip().upper()
    if not _COUNTRY_CODE.match(value) or value in _UNKNOWN_COUNTRY_CODES:
        return None
    return value


def ad_pixels_allowed(request: HttpRequest) -> bool:
    """Whether the Meta and TikTok pixels may load for this request.

    Refused on any educator_interface page: no other staff-only page extends
    _base.html, so this is the only namespace that needs naming here.
    """
    match = request.resolver_match
    if match is not None and "educator_interface" in match.app_names:
        return False
    country = visitor_country(request)
    return country is not None and country not in EU_CONSENT_POLICY_COUNTRIES


class PixelCall(NamedTuple):
    """One platform call for an analytics event."""

    method: str  # e.g. "track" or "trackCustom"
    name: str  # the platform's event name
    # Parameters the analytics event must carry for the row to apply.
    condition: Mapping[str, str] = {}


def pixel_call(
    mapping: Mapping[str, PixelCall], event: AnalyticsEventPayload
) -> PixelCall | None:
    """The platform call for `event` per `mapping`, or None when it does not apply.

    An unmapped event name, or one whose parameters don't match the row's
    condition (e.g. an interest registration where only an application
    should fire), gives None.
    """
    call = mapping.get(event["name"])
    if call is None:
        return None
    if any(event["params"].get(key) != value for key, value in call.condition.items()):
        return None
    return call
