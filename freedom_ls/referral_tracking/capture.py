"""Sanitising query-parameter capture and the signed attribution cookie."""

from __future__ import annotations

import base64
import json
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser
from django.http import HttpRequest
from django.http.response import HttpResponseBase
from django.utils import timezone

from freedom_ls.referral_tracking.config import config
from freedom_ls.referral_tracking.counters import (
    attribution_key_hash_of,
    attribution_key_values,
)
from freedom_ls.referral_tracking.models import (
    ATTRIBUTION_KEY_FIELDS,
    CAPS,
    SignupAttribution,
)

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
    "ref",
)
LOWERCASED_PARAMS = ("utm_source", "utm_medium")
COOKIE_SALT = "freedom_ls.referral_tracking"

# Short cookie keys, one per frozen field plus the landing time.
COOKIE_KEYS: dict[str, str] = {
    "advert_code": "a",
    "referral_code": "rc",
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

# The later landings the cookie remembers beside the first touch. Kept out of
# COOKIE_KEYS: `t` is taken there by utm_term, and downstream projects build
# model fields from COOKIE_KEYS, so a new entry would break them.
COOKIE_TOUCHES_KEY = "tl"

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

_CAPTURE_SUPPRESSED_ATTR = "_attribution_capture_suppressed"


def suppress_capture(request: HttpRequest) -> None:
    """Opt this request out of minting the cookie or tallying a first touch.

    The referral redirect routes call this before anything else, so a 404 on
    one of them never mints either.
    """
    setattr(request, _CAPTURE_SUPPRESSED_ATTR, True)


def is_capture_suppressed(request: HttpRequest) -> bool:
    return getattr(request, _CAPTURE_SUPPRESSED_ATTR, False) is True


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
    """Every frozen field for this landing, sanitised, plus first_seen as ISO 8601.

    `ref` is the one tracked parameter whose field name differs from the
    query parameter that fills it: it lands in `referral_code`, never looked
    up against `ReferralCode`, so a hand-typed `?ref=anything` is stored as
    free text the way `advert_code` is.
    """
    first_touch = {
        name: sanitise(
            request.GET.get(name, ""), CAPS[name], lower=name in LOWERCASED_PARAMS
        )
        for name in TRACKED_PARAMS
        if name != "ref"
    }
    first_touch["referral_code"] = sanitise(
        request.GET.get("ref", ""), CAPS["referral_code"]
    )
    first_touch["landing_path"] = sanitise(request.path, CAPS["landing_path"])
    first_touch["referer"] = sanitise(
        request.headers.get("Referer", ""), CAPS["referer"]
    )
    first_touch["raw_query"] = sanitise(
        request.META.get("QUERY_STRING", ""), CAPS["raw_query"]
    )
    first_touch["first_seen"] = timezone.now().isoformat()
    return first_touch


@dataclass(frozen=True)
class CookieTouch:
    """One landing the cookie remembers: the attribution key and when it happened.

    `landing_path` is set only for the frozen first touch; list entries leave
    it blank to keep the cookie small.
    """

    advert_code: str
    utm_source: str
    utm_medium: str
    utm_campaign: str
    utm_content: str
    utm_term: str
    referral_code: str
    occurred_at: datetime
    landing_path: str = ""

    @property
    def key_fields(self) -> dict[str, str]:
        return {name: getattr(self, name) for name in ATTRIBUTION_KEY_FIELDS}

    @property
    def key_values(self) -> tuple[str, ...]:
        return attribution_key_values(self.key_fields)

    @property
    def key_hash(self) -> str:
        return attribution_key_hash_of(self.key_fields)


def _cookie_max_age() -> int:
    return config.REFERRAL_TRACKING_COOKIE_MAX_AGE_DAYS * 86400


def _parse_cookie_time(text: str) -> datetime | None:
    """The aware time `text` holds, or None when it is unparseable or naive.

    A naive time would raise `TypeError` the first time it is compared with
    `timezone.now()`, which could happen inside a signal receiver.
    """
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.utcoffset() is None:
        return None
    return parsed


_PayloadValue = str | list[dict[str, str]]


def _encode_payload(payload: Mapping[str, _PayloadValue]) -> str:
    # ensure_ascii=False keeps a CJK character at 3 bytes rather than the 6 of
    # its \uXXXX escape; the value is base64 either way, so it stays token-safe.
    return base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).decode("ascii")


def _touch_entry_payload(touch: CookieTouch) -> dict[str, str]:
    entry = {
        COOKIE_KEYS[name]: value for name, value in touch.key_fields.items() if value
    }
    entry[COOKIE_KEYS["first_seen"]] = touch.occurred_at.isoformat()
    return entry


def set_attribution_cookie(
    response: HttpResponseBase,
    first_touch: dict[str, str],
    *,
    touches: Sequence[CookieTouch] = (),
) -> bool:
    """Set the cookie and return True, or return False when it cannot fit.

    A browser drops an oversize cookie without saying so, and a visitor whose
    cookie never sticks would be minted and tallied again on every landing.
    The fields that are not part of the attribution key are dropped from the
    first touch in order of value until the payload fits; then list entries
    go, oldest first, but never the newest. A payload that still does not fit
    is not set at all, and the caller must not count it as a first touch.

    Expiry is counted from the first touch, not from now, so appending to the
    list never extends how long the cookie lives. A cookie at exactly the
    limit gets a `max_age` of 0, which the browser treats as expiry.
    """
    payload: dict[str, _PayloadValue] = {
        COOKIE_KEYS[name]: value for name, value in first_touch.items() if value
    }
    entries = [_touch_entry_payload(touch) for touch in touches]

    def encode() -> str:
        if entries:
            payload[COOKIE_TOUCHES_KEY] = entries
        return _encode_payload(payload)

    encoded = encode()
    for name in COOKIE_DROP_ORDER:
        if len(encoded) <= COOKIE_MAX_ENCODED_LENGTH:
            break
        payload.pop(COOKIE_KEYS[name], None)
        encoded = encode()
    while len(encoded) > COOKIE_MAX_ENCODED_LENGTH and len(entries) > 1:
        entries.pop(0)
        encoded = encode()
    if len(encoded) > COOKIE_MAX_ENCODED_LENGTH:
        return False
    response.set_signed_cookie(
        config.REFERRAL_TRACKING_COOKIE_NAME,
        encoded,
        salt=COOKIE_SALT,
        max_age=_remaining_max_age(first_touch["first_seen"]),
        httponly=True,
        samesite="Lax",
        secure=settings.SESSION_COOKIE_SECURE,
    )
    return True


def _remaining_max_age(first_seen: str) -> int:
    first_seen_at = _parse_cookie_time(first_seen) or timezone.now()
    elapsed = int((timezone.now() - first_seen_at).total_seconds())
    return max(0, _cookie_max_age() - elapsed)


_DecodedCookie = tuple[dict[str, str], list[CookieTouch]]
_DECODED_ATTR = "_attribution_cookie_decoded"


def _decode_cookie(request: HttpRequest) -> _DecodedCookie | None:
    """The validated cookie contents, decoded once per request.

    Readers copy what they take from here, so one caller changing the dict it
    gets back cannot change what the next reader sees.
    """
    if hasattr(request, _DECODED_ATTR):
        decoded: _DecodedCookie | None = getattr(request, _DECODED_ATTR)
        return decoded
    decoded = _decode_cookie_uncached(request)
    setattr(request, _DECODED_ATTR, decoded)
    return decoded


def _decode_cookie_uncached(request: HttpRequest) -> _DecodedCookie | None:
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
    first_seen = datetime.fromisoformat(payload[COOKIE_KEYS["first_seen"]])
    # Signing is re-done on every re-set, so the signature's age alone would
    # let a cookie that keeps being appended to outlive its first touch.
    if timezone.now() - first_seen > timedelta(
        days=config.REFERRAL_TRACKING_COOKIE_MAX_AGE_DAYS
    ):
        return None
    first = {key: value for key, value in payload.items() if key != COOKIE_TOUCHES_KEY}
    touches = [
        _touch_from_entry(entry) for entry in payload.get(COOKIE_TOUCHES_KEY, [])
    ]
    return first, touches


def _touch_from_entry(entry: dict[str, str]) -> CookieTouch:
    short_to_name = {short: name for name, short in COOKIE_KEYS.items()}
    fields = {short_to_name[short]: value for short, value in entry.items()}
    return CookieTouch(
        **{name: fields.get(name, "") for name in ATTRIBUTION_KEY_FIELDS},
        occurred_at=datetime.fromisoformat(entry[COOKIE_KEYS["first_seen"]]),
    )


def read_attribution_cookie(request: HttpRequest) -> dict[str, str] | None:
    """The first touch the cookie carries, or None for absent, expired, forged or unparseable."""
    decoded = _decode_cookie(request)
    if decoded is None:
        return None
    first, _ = decoded
    return {name: first.get(short, "") for name, short in COOKIE_KEYS.items()}


def read_cookie_touches(request: HttpRequest) -> list[CookieTouch]:
    """The later landings the cookie carries, oldest first; empty when there are none."""
    decoded = _decode_cookie(request)
    if decoded is None:
        return []
    _, touches = decoded
    return list(touches)


def append_touch(
    touches: Sequence[CookieTouch],
    first_touch: dict[str, str],
    request: HttpRequest,
) -> list[CookieTouch] | None:
    """The touch list with this landing added, or None when it adds nothing.

    A landing adds nothing when every attribution field is blank (a click id
    alone) or when it repeats the latest key. `first_touch` is the cookie's
    frozen first touch, which stands in as the latest key while the list is
    empty. The list is bounded: the oldest entry is evicted first.
    """
    landing = first_touch_from_request(request)
    landing_values = attribution_key_values(landing)
    if not any(landing_values):
        return None
    latest_values = (
        touches[-1].key_values if touches else attribution_key_values(first_touch)
    )
    if landing_values == latest_values:
        return None
    entry = CookieTouch(
        **{name: landing[name] for name in ATTRIBUTION_KEY_FIELDS},
        occurred_at=datetime.fromisoformat(landing["first_seen"]),
    )
    return [*touches, entry][-config.REFERRAL_TRACKING_MAX_COOKIE_TOUCHES :]


def _is_touch_list(value: object) -> bool:
    """A list of dicts keyed by the attribution short keys or `ts`, all str, with a parseable `ts`."""
    if not isinstance(value, list):
        return False
    allowed = {COOKIE_KEYS[name] for name in ATTRIBUTION_KEY_FIELDS}
    allowed.add(COOKIE_KEYS["first_seen"])
    for entry in value:
        if not isinstance(entry, dict):
            return False
        if any(
            key not in allowed or not isinstance(item, str)
            for key, item in entry.items()
        ):
            return False
        time_text = entry.get(COOKIE_KEYS["first_seen"])
        if time_text is None or _parse_cookie_time(time_text) is None:
            return False
    return True


def _is_first_touch_payload(payload: object) -> bool:
    """A JSON object whose keys are all short keys, whose values are all str
    (except the touch list), and whose landing time parses."""
    if not isinstance(payload, dict):
        return False
    known = set(COOKIE_KEYS.values())
    for key, value in payload.items():
        if key == COOKIE_TOUCHES_KEY:
            if not _is_touch_list(value):
                return False
        elif key not in known or not isinstance(value, str):
            return False
    first_seen = payload.get(COOKIE_KEYS["first_seen"])
    return isinstance(first_seen, str) and _parse_cookie_time(first_seen) is not None


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
