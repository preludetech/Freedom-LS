"""Referral code text, its reserved words, and the site paths a code can redirect to."""

from __future__ import annotations

import re
import secrets
from typing import TYPE_CHECKING
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError
from django.db.models.functions import Lower
from django.urls import Resolver404, resolve, reverse
from django.utils.text import slugify

from freedom_ls.referral_tracking.config import config

if TYPE_CHECKING:
    from freedom_ls.referral_tracking.models import Door, ReferralCode

CODE_PATTERN = re.compile(r"[A-Za-z0-9-]{1,64}")
GENERATED_CODE_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"  # pragma: allowlist secret
GENERATED_CODE_LENGTH = 8
GENERATED_CODE_ATTEMPTS = 20
RESERVED_REFERRAL_CODES = frozenset(
    {
        "admin",
        "api",
        "account",
        "accounts",
        "login",
        "logout",
        "signup",
        "register",
        "support",
        "help",
        "contact",
        "security",
        "billing",
        "official",
        "staff",
        "static",
        "media",
        "www",
        "mail",
    }
)


def validate_code_text(code: str, site: Site) -> None:
    if not CODE_PATTERN.fullmatch(code):
        raise ValidationError("Use 1 to 64 letters, digits or hyphens.")
    lowered = code.lower()
    if lowered in RESERVED_REFERRAL_CODES:
        raise ValidationError(f"{code!r} is reserved. Choose a different code.")
    brand = slugify(site.name) if site.name else ""
    if brand and lowered in {brand, brand.replace("-", "")}:
        raise ValidationError(
            "The site's own name is reserved. Choose a different code."
        )


def lookup_referral_code(site: Site, code: str) -> ReferralCode | None:
    from freedom_ls.referral_tracking.models import ReferralCode

    # _base_manager, not `objects`: the site-aware manager also ANDs in the
    # ambient request's site, and generate_code may be probing another.
    return (
        ReferralCode._base_manager.filter(site=site)
        .alias(code_lower=Lower("code"))
        .filter(code_lower=code.lower())
        .first()
    )


def generate_code(site: Site) -> str:
    for _ in range(GENERATED_CODE_ATTEMPTS):
        candidate = "".join(
            secrets.choice(GENERATED_CODE_ALPHABET)
            for _ in range(GENERATED_CODE_LENGTH)
        )
        try:
            validate_code_text(candidate, site)
        except ValidationError:
            continue
        if lookup_referral_code(site, candidate) is None:
            return candidate
    raise ValidationError("Could not find an unused code. Save again.")


def validate_site_path(value: str) -> None:
    if not value.startswith("/") or value[1:2] in ("/", "\\"):
        raise ValidationError("Enter a path on this site, starting with a single '/'.")
    if any(ch.isspace() or ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValidationError(
            "A path cannot contain whitespace or control characters. Remove them."
        )
    path = urlsplit(value).path
    try:
        match = resolve(path)
    except Resolver404:
        return
    from freedom_ls.referral_tracking.views import follow_referral_code

    if match.func is follow_referral_code:
        raise ValidationError(
            "A destination cannot be a referral code route. Point it at a page."
        )


def inactive_destination_for(referral_code: ReferralCode) -> str:
    return (
        referral_code.inactive_destination
        or config.REFERRAL_TRACKING_INACTIVE_DESTINATION
    )


def build_redirect_url(
    referral_code: ReferralCode, query_string: str, *, base: str | None = None
) -> str:
    if base is None:
        base = (
            referral_code.destination
            if referral_code.is_active
            else inactive_destination_for(referral_code)
        )
    parts = urlsplit(base)
    visitor = [
        (k, v) for k, v in parse_qsl(query_string, keep_blank_values=True) if k != "ref"
    ]
    visitor_keys = {k for k, _ in visitor}
    kept = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k != "ref" and k not in visitor_keys
    ]
    query = urlencode([*kept, *visitor, ("ref", referral_code.code)])
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))


def absolute_code_url(referral_code: ReferralCode, door: Door) -> str:
    from freedom_ls.referral_tracking.models import Door

    protocol = getattr(settings, "ACCOUNT_DEFAULT_HTTP_PROTOCOL", "https")
    url_name = (
        "referral_tracking:follow_go"
        if door == Door.GO
        else "referral_tracking:follow_d"
    )
    path = reverse(url_name, kwargs={"code": referral_code.code})
    url = f"{protocol}://{referral_code.site.domain}{path}"
    return url.upper() if door == Door.D else url
