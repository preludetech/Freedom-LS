"""Detecting a machine fetch and logging one access of a referral code."""

from __future__ import annotations

import re

import sentry_sdk

from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, transaction
from django.db.models import F
from django.http import HttpRequest
from django.utils import timezone
from django.utils.crypto import salted_hmac

from freedom_ls.accounts.utils import get_client_ip
from freedom_ls.referral_tracking.config import config
from freedom_ls.referral_tracking.models import Door, ReferralCode, ReferralCodeHit

NAMED_FETCHERS = (
    "slackbot",
    "facebookexternalhit",
    "twitterbot",
    "whatsapp",
    "telegrambot",
    "discordbot",
    "linkedinbot",
    "googlebot",
    "bingbot",
    "applebot",
    "skypeuripreview",
)
GENERIC_TOKENS = ("crawler", "spider", "preview", "headless")
BOT_WORD = re.compile(r"\bbot\b")
PREFETCH_HEADERS = ("Sec-Purpose", "Purpose", "X-Moz")


def is_machine_fetch(request: HttpRequest) -> bool:
    user_agent = request.headers.get("User-Agent", "").lower()
    if not user_agent:
        return True
    if any(name in user_agent for name in NAMED_FETCHERS):
        return True
    if any(token in user_agent for token in GENERIC_TOKENS) or BOT_WORD.search(
        user_agent
    ):
        return True
    return any(
        "prefetch" in request.headers.get(header, "").lower()
        for header in PREFETCH_HEADERS
    )


def _client_fingerprint(ip: str) -> str:
    """A per-deployment pseudonym for one client address.

    The cache key reaches storage — under the default DatabaseCache it is a
    row in the cache table — so the address must not be readable from it. A
    plain digest would not do: the IPv4 space is small enough to exhaust, so
    this is keyed on SECRET_KEY.
    """
    return salted_hmac("referral_tracking.hit_log", ip).hexdigest()[:32]


def is_hit_log_throttled(referral_code: ReferralCode, request: HttpRequest) -> bool:
    """Whether this client has already had its fill of logged hits on this code.

    `/go/` and `/d/` are anonymous and write a row per request, so without a cap
    anyone holding one valid code can grow the hit log without bound. A throttled
    hit is not logged and does not move `hit_count`; the visitor is redirected
    either way, since these codes get printed on boards and scanned by a crowd
    behind one address, and refusing the redirect would break the link itself.
    """
    limit = config.REFERRAL_TRACKING_HIT_LOG_LIMIT
    window = config.REFERRAL_TRACKING_HIT_LOG_WINDOW_SECONDS
    if limit <= 0 or window <= 0:
        return False
    try:
        ip = get_client_ip(request)
    except PermissionDenied:
        # A configured proxy header is missing, so the edge was bypassed or is
        # misconfigured. Log the hit rather than silently dropping every one:
        # signup already refuses outright on the same deployment fault, so it
        # does not go unnoticed.
        return False
    if not ip:
        return False
    # A key per window, rather than one key whose expiry is pushed out: on a
    # backend without a native incr, `cache.incr` is get-then-set and resets
    # the timeout, so a steady stream would keep one counter alive for good.
    bucket = int(timezone.now().timestamp()) // window
    key = (
        f"referral-hit:{referral_code.site_id}:{referral_code.pk}"
        f":{_client_fingerprint(ip)}:{bucket}"
    )
    if cache.add(key, 1, window * 2):
        return False
    try:
        count = cache.incr(key)
    except ValueError:
        # The bucket expired between the add and the incr.
        return False
    return bool(count > limit)


def record_hit(referral_code: ReferralCode, door: Door, request: HttpRequest) -> None:
    machine_fetch = is_machine_fetch(request)
    try:
        if is_hit_log_throttled(referral_code, request):
            return
        with transaction.atomic():
            ReferralCodeHit._base_manager.create(
                site_id=referral_code.site_id,
                referral_code=referral_code,
                door=door,
                is_machine_fetch=machine_fetch,
            )
            if not machine_fetch:
                ReferralCode._base_manager.filter(pk=referral_code.pk).update(
                    hit_count=F("hit_count") + 1, last_hit_at=timezone.now()
                )
    except DatabaseError as exc:
        sentry_sdk.capture_exception(exc)
