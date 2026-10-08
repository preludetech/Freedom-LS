"""Detecting a machine fetch and logging one access of a referral code."""

from __future__ import annotations

import re

import sentry_sdk

from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, transaction
from django.db.models import F
from django.http import HttpRequest
from django.utils import timezone

from freedom_ls.accounts.throttling import is_ip_throttled
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


def is_hit_log_throttled(referral_code: ReferralCode, request: HttpRequest) -> bool:
    """Whether this client has already had its fill of logged hits on this code.

    `/go/` and `/d/` are anonymous and write a row per request, so without a cap
    anyone holding one valid code can grow the hit log without bound. A throttled
    hit is not logged and does not move `hit_count`; the visitor is redirected
    either way, since these codes get printed on boards and scanned by a crowd
    behind one address, and refusing the redirect would break the link itself.
    """
    try:
        return is_ip_throttled(
            request,
            namespace="referral_tracking.hit_log",
            scope=f"{referral_code.site_id}:{referral_code.pk}",
            limit=config.REFERRAL_TRACKING_HIT_LOG_LIMIT,
            window_seconds=config.REFERRAL_TRACKING_HIT_LOG_WINDOW_SECONDS,
        )
    except PermissionDenied:
        # A configured proxy header is missing, so the edge was bypassed or is
        # misconfigured. Log the hit rather than silently dropping every one:
        # signup already refuses outright on the same deployment fault, so it
        # does not go unnoticed.
        return False


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
