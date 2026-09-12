"""Detecting a machine fetch and logging one access of a referral code."""

from __future__ import annotations

import re

import sentry_sdk

from django.db import DatabaseError, transaction
from django.db.models import F
from django.http import HttpRequest
from django.utils import timezone

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


def record_hit(referral_code: ReferralCode, door: Door, request: HttpRequest) -> None:
    machine_fetch = is_machine_fetch(request)
    try:
        with transaction.atomic():
            ReferralCodeHit._base_manager.create(
                site=referral_code.site,
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
