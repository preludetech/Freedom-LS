"""Sanitising query-parameter capture and the signed attribution cookie."""

from __future__ import annotations

import base64
import json
import unicodedata
from datetime import datetime

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser
from django.http import HttpRequest
from django.http.response import HttpResponseBase
from django.utils import timezone

from freedom_ls.referral_tracking.config import config
from freedom_ls.referral_tracking.models import CAPS, SignupAttribution

TRACKED_PARAMS = (
    "advert_code",
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_content",
    "utm_term",
    "gclid",
    "gbraid",
    "wbraid",
    "fbclid",
)
LOWERCASED_PARAMS = ("utm_source", "utm_medium")
COOKIE_SALT = "freedom_ls.referral_tracking"

# Short cookie keys, one per frozen field plus the landing time.
COOKIE_KEYS: dict[str, str] = {
    "advert_code": "a",
    "utm_source": "s",
    "utm_medium": "m",
    "utm_campaign": "c",
    "utm_content": "n",
    "utm_term": "t",
    "gclid": "g",
    "gbraid": "gb",
    "wbraid": "wb",
    "fbclid": "f",
    "landing_path": "p",
    "referer": "r",
    "raw_query": "q",
    "first_seen": "ts",
}

# Browsers hold a cookie to 4096 bytes of name plus value. The signer appends
# a timestamp and signature of about 55 bytes and the default name is 16, so
# the encoded payload itself gets a little under 3.9KB.
COOKIE_MAX_ENCODED_LENGTH = 3800
# Dropped from the payload, in this order, until it fits. A multi-byte campaign
# at the caps is over after the first two; only an all-multi-byte payload — one
# whose click ids are not click ids — gets past them. None of these is part of
# the attribution key, so the cookie and the tally still agree.
COOKIE_DROP_ORDER = (
    "raw_query",
    "referer",
    "landing_path",
    "fbclid",
    "wbraid",
    "gbraid",
    "gclid",
)

_CONTROL_CHARS = dict.fromkeys((*range(0, 32), 127))


def sanitise(value: str, cap: int, *, lower: bool = False) -> str:
    # No unquote(): request.GET is already decoded, and decoding again would
    # corrupt a legitimate %2B or smuggle characters past this filter.
    value = value.translate(_CONTROL_CHARS)
    value = unicodedata.normalize("NFC", value).strip()
    if lower:
        value = value.lower()
    return value[:cap]


def has_tracked_params(request: HttpRequest) -> bool:
    return any(name in request.GET for name in TRACKED_PARAMS)


def first_touch_from_request(request: HttpRequest) -> dict[str, str]:
    """Every frozen field for this landing, sanitised, plus first_seen as ISO 8601."""
    first_touch = {
        name: sanitise(
            request.GET.get(name, ""), CAPS[name], lower=name in LOWERCASED_PARAMS
        )
        for name in TRACKED_PARAMS
    }
    first_touch["landing_path"] = sanitise(request.path, CAPS["landing_path"])
    first_touch["referer"] = sanitise(
        request.headers.get("Referer", ""), CAPS["referer"]
    )
    first_touch["raw_query"] = sanitise(
        request.META.get("QUERY_STRING", ""), CAPS["raw_query"]
    )
    first_touch["first_seen"] = timezone.now().isoformat()
    return first_touch


def _cookie_max_age() -> int:
    return config.REFERRAL_TRACKING_COOKIE_MAX_AGE_DAYS * 86400


def _encode_payload(payload: dict[str, str]) -> str:
    # ensure_ascii=False keeps a CJK character at 3 bytes rather than the 6 of
    # its \uXXXX escape; the value is base64 either way, so it stays token-safe.
    return base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).decode("ascii")


def set_attribution_cookie(
    response: HttpResponseBase, first_touch: dict[str, str]
) -> bool:
    """Set the cookie and return True, or return False when it cannot fit.

    A browser drops an oversize cookie without saying so, and a visitor whose
    cookie never sticks would be minted and tallied again on every landing.
    The fields that are not part of the attribution key are dropped in order
    of value until the payload fits; a payload that still does not fit is not
    set at all, and the caller must not count it as a first touch.
    """
    payload = {COOKIE_KEYS[name]: value for name, value in first_touch.items() if value}
    encoded = _encode_payload(payload)
    for name in COOKIE_DROP_ORDER:
        if len(encoded) <= COOKIE_MAX_ENCODED_LENGTH:
            break
        payload.pop(COOKIE_KEYS[name], None)
        encoded = _encode_payload(payload)
    if len(encoded) > COOKIE_MAX_ENCODED_LENGTH:
        return False
    response.set_signed_cookie(
        config.REFERRAL_TRACKING_COOKIE_NAME,
        encoded,
        salt=COOKIE_SALT,
        max_age=_cookie_max_age(),
        httponly=True,
        samesite="Lax",
        secure=settings.SESSION_COOKIE_SECURE,
    )
    return True


def read_attribution_cookie(request: HttpRequest) -> dict[str, str] | None:
    """The first touch the cookie carries, or None for absent, expired, forged or unparseable."""
    encoded = request.get_signed_cookie(
        config.REFERRAL_TRACKING_COOKIE_NAME,
        default=None,
        salt=COOKIE_SALT,
        max_age=_cookie_max_age(),
    )
    if encoded is None:
        return None
    try:
        payload = json.loads(base64.urlsafe_b64decode(encoded))
    except (
        ValueError
    ):  # binascii.Error, UnicodeDecodeError and JSONDecodeError all subclass it
        return None
    if not _is_first_touch_payload(payload):
        return None
    return {name: payload.get(short, "") for name, short in COOKIE_KEYS.items()}


def _is_first_touch_payload(payload: object) -> bool:
    """A JSON object whose keys are all short keys, whose values are all str, and whose
    landing time parses."""
    if not isinstance(payload, dict):
        return False
    known = set(COOKIE_KEYS.values())
    if any(
        key not in known or not isinstance(value, str) for key, value in payload.items()
    ):
        return False
    try:
        datetime.fromisoformat(payload.get("ts", ""))
    except ValueError:
        return False
    return True


def record_signup_attribution(
    *, request: HttpRequest, user: AbstractBaseUser, client_ip: str | None
) -> SignupAttribution:
    """Write the one SignupAttribution row for this signup.

    Where the attribution cookie is absent, expired or unreadable, the
    landing is recorded as direct traffic rather than left blank, so "we
    don't know where this came from" is a channel like any other.
    """
    first_touch = read_attribution_cookie(request)
    now = timezone.now()
    frozen: dict[str, str]
    if first_touch is None:
        frozen = {"utm_source": "direct", "utm_medium": "none"}
        first_seen = now
    else:
        first_seen = datetime.fromisoformat(first_touch.pop("first_seen"))
        frozen = first_touch
    attribution: SignupAttribution = SignupAttribution.objects.create(
        user=user,
        first_seen=first_seen,
        ga_cookie=sanitise(request.COOKIES.get("_ga", ""), CAPS["ga_cookie"]),
        fbp_cookie=sanitise(request.COOKIES.get("_fbp", ""), CAPS["fbp_cookie"]),
        fbc_cookie=sanitise(request.COOKIES.get("_fbc", ""), CAPS["fbc_cookie"]),
        client_ip=client_ip,
        user_agent=sanitise(request.headers.get("User-Agent", ""), CAPS["user_agent"]),
        **frozen,
    )
    return attribution
