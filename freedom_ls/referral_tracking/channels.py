"""The marketing channel a first touch came through, worked out from its stored fields.

Pure: no request and no database query. Callers classify at read time, so a rule
change reclassifies history.
"""

import re
from dataclasses import dataclass, fields
from datetime import datetime
from typing import Protocol

from django.db import models

from freedom_ls.referral_tracking.referers import referer_host


class Channel(models.TextChoices):
    # Declaration order is the display order: `.choices` feeds filter dropdowns.
    DIRECT = "direct", "Direct"
    ORGANIC_SEARCH = "organic_search", "Organic search"
    PAID_SEARCH = "paid_search", "Paid search"
    ORGANIC_SOCIAL = "organic_social", "Organic social"
    PAID_SOCIAL = "paid_social", "Paid social"
    EMAIL = "email", "Email"
    REFERRAL = "referral", "Referral"
    OTHER = "other", "Other"
    UNKNOWN = "unknown", "Unknown"


class ChannelBasis(models.TextChoices):
    UTM = "utm", "UTM tags"
    GCLID = "gclid", "Google click ID"
    REFERER = "referer", "Referring site"
    REFERRAL_CODE = "referral_code", "Referral code"
    FBCLID_ONLY = "fbclid_only", "Meta click ID only"
    NONE = "none", "No signal"


class FirstTouchFields(Protocol):
    """Any record with the first-touch field names, such as `SignupAttribution`
    or a project's own lead model."""

    advert_code: str
    referral_code: str
    utm_source: str
    utm_medium: str
    utm_campaign: str
    utm_content: str
    utm_term: str
    gclid: str
    gbraid: str
    wbraid: str
    fbclid: str
    landing_path: str
    referer: str
    raw_query: str


@dataclass(frozen=True)
class FirstTouch:
    advert_code: str
    referral_code: str
    utm_source: str
    utm_medium: str
    utm_campaign: str
    utm_content: str
    utm_term: str
    gclid: str
    gbraid: str
    wbraid: str
    fbclid: str
    landing_path: str
    referer: str
    raw_query: str
    first_seen: datetime

    @classmethod
    def from_record(
        cls, record: FirstTouchFields, first_seen: datetime
    ) -> "FirstTouch":
        names = [f.name for f in fields(cls) if f.name != "first_seen"]
        return cls(
            **{name: getattr(record, name) for name in names}, first_seen=first_seen
        )


@dataclass(frozen=True)
class ChannelResult:
    channel: Channel
    source_platform: str
    basis: ChannelBasis


DIRECT_SOURCES: frozenset[str] = frozenset({"direct", "(direct)"})
DIRECT_MEDIA: frozenset[str] = frozenset({"none", "(none)", "(not set)"})
PAID_MEDIUM = re.compile(r"^(.*cp.*|ppc|retargeting|paid.*)$")
VIDEO_MEDIUM = re.compile(r"^(.*video.*)$")
DISPLAY_MEDIA: frozenset[str] = frozenset(
    {"display", "banner", "expandable", "interstitial", "cpm"}
)
SOCIAL_MEDIA: frozenset[str] = frozenset(
    {"social", "social-network", "social-media", "sm", "social network", "social media"}
)
EMAIL_VALUES: frozenset[str] = frozenset({"email", "e-mail", "e_mail", "e mail"})
REFERRAL_MEDIA: frozenset[str] = frozenset({"referral", "app", "link", "affiliate"})

SEARCH_SOURCES: dict[str, str] = {
    "google": "Google",
    "bing": "Bing",
    "duckduckgo": "DuckDuckGo",
    "yahoo": "Yahoo",
    "ecosia": "Ecosia",
    "baidu": "Baidu",
    "yandex": "Yandex",
    "qwant": "Qwant",
    "ask": "Ask",
    "aol": "AOL",
    "naver": "Naver",
    "seznam": "Seznam",
    "sogou": "Sogou",
    "daum": "Daum",
    "msn": "MSN",
}
SOCIAL_SOURCES: dict[str, str] = {
    "facebook": "Facebook",
    "fb": "Facebook",
    "instagram": "Instagram",
    "ig": "Instagram",
    "an": "Meta",
    "msg": "Meta",
    "messenger": "Meta",
    "tiktok": "TikTok",
    "tt": "TikTok",
    "x": "X",
    "twitter": "X",
    "linkedin": "LinkedIn",
    "whatsapp": "WhatsApp",
    "pinterest": "Pinterest",
    "reddit": "Reddit",
    "snapchat": "Snapchat",
    "tumblr": "Tumblr",
    "quora": "Quora",
    "vk": "VK",
    "weibo": "Weibo",
    "wechat": "WeChat",
    "line": "Line",
}
VIDEO_SOURCES: dict[str, str] = {
    "youtube": "YouTube",
    "vimeo": "Vimeo",
    "twitch": "Twitch",
    "dailymotion": "Dailymotion",
}

_SOCIAL_AND_VIDEO_SOURCES: dict[str, str] = {**SOCIAL_SOURCES, **VIDEO_SOURCES}

SEARCH_HOSTS: dict[str, str] = {
    "bing.com": "Bing",
    "duckduckgo.com": "DuckDuckGo",
    "yahoo.com": "Yahoo",
    "yahoo.co.jp": "Yahoo",
    "ecosia.org": "Ecosia",
    "baidu.com": "Baidu",
    "yandex.com": "Yandex",
    "yandex.ru": "Yandex",
    "qwant.com": "Qwant",
    "ask.com": "Ask",
    "aol.com": "AOL",
    "naver.com": "Naver",
    "seznam.cz": "Seznam",
    "sogou.com": "Sogou",
    "msn.com": "MSN",
    "search.google.com": "Google",
    "lens.google.com": "Google",
    "news.google.com": "Google",
    "play.google.com": "Google",
}
SOCIAL_HOSTS: dict[str, str] = {
    "facebook.com": "Facebook",
    "fb.com": "Facebook",
    "fb.me": "Facebook",
    "instagram.com": "Instagram",
    "messenger.com": "Meta",
    "t.co": "X",
    "twitter.com": "X",
    "x.com": "X",
    "linkedin.com": "LinkedIn",
    "lnkd.in": "LinkedIn",
    "tiktok.com": "TikTok",
    "pinterest.com": "Pinterest",
    "reddit.com": "Reddit",
    "whatsapp.com": "WhatsApp",
    "wa.me": "WhatsApp",
    "snapchat.com": "Snapchat",
    "tumblr.com": "Tumblr",
    "quora.com": "Quora",
    "vk.com": "VK",
    "weibo.com": "Weibo",
    "wechat.com": "WeChat",
}
VIDEO_HOSTS: dict[str, str] = {
    "youtube.com": "YouTube",
    "youtu.be": "YouTube",
    "vimeo.com": "Vimeo",
    "twitch.tv": "Twitch",
    "dailymotion.com": "Dailymotion",
}
EMAIL_HOSTS: dict[str, str] = {
    "mail.google.com": "Gmail",
    "mail.yahoo.com": "Yahoo Mail",
    "outlook.live.com": "Outlook",
    "outlook.office.com": "Outlook",
    "outlook.office365.com": "Outlook",
    "mail.proton.me": "Proton Mail",
    "icloud.com": "iCloud Mail",
}
GOOGLE_SEARCH_HOST = re.compile(r"^google\.([a-z]{2,3}|co\.[a-z]{2}|com\.[a-z]{2})$")
APP_PACKAGES: dict[str, tuple[Channel, str]] = {
    "com.facebook.katana": (Channel.ORGANIC_SOCIAL, "Facebook"),
    "com.facebook.lite": (Channel.ORGANIC_SOCIAL, "Facebook"),
    "com.facebook.orca": (Channel.ORGANIC_SOCIAL, "Meta"),
    "com.instagram.android": (Channel.ORGANIC_SOCIAL, "Instagram"),
    "com.whatsapp": (Channel.ORGANIC_SOCIAL, "WhatsApp"),
    "com.twitter.android": (Channel.ORGANIC_SOCIAL, "X"),
    "com.linkedin.android": (Channel.ORGANIC_SOCIAL, "LinkedIn"),
    "com.zhiliaoapp.musically": (Channel.ORGANIC_SOCIAL, "TikTok"),
    "com.pinterest": (Channel.ORGANIC_SOCIAL, "Pinterest"),
    "com.reddit.frontpage": (Channel.ORGANIC_SOCIAL, "Reddit"),
    "com.snapchat.android": (Channel.ORGANIC_SOCIAL, "Snapchat"),
    "org.telegram.messenger": (Channel.ORGANIC_SOCIAL, "Telegram"),
    "com.google.android.youtube": (Channel.ORGANIC_SOCIAL, "YouTube"),
    "com.google.android.googlequicksearchbox": (Channel.ORGANIC_SEARCH, "Google"),
    "com.google.android.gm": (Channel.EMAIL, "Gmail"),
    "com.microsoft.office.outlook": (Channel.EMAIL, "Outlook"),
}

_ANDROID_APP_PREFIX = "android-app://"


def is_direct_pair(utm_source: str, utm_medium: str) -> bool:
    """True when the source is a direct marker and the medium is an empty marker."""
    return (
        utm_source.strip().lower() in DIRECT_SOURCES
        and utm_medium.strip().lower() in DIRECT_MEDIA
    )


def _matches(host: str, listed: str) -> bool:
    return host == listed or host.endswith("." + listed)


def _lookup(host: str, table: dict[str, str]) -> str | None:
    """The platform for the first listed name that the host equals or sits under."""
    for listed, platform in table.items():
        if _matches(host, listed):
            return platform
    return None


def _utm_signal(first_touch: FirstTouch) -> tuple[str, str] | None:
    """The stripped, lowercased UTM pair, or None when it says nothing.

    Normalised here because rows written outside capture may differ in case or
    whitespace, and `classify` and `has_signal` must agree on what counts."""
    source = first_touch.utm_source.strip().lower()
    medium = first_touch.utm_medium.strip().lower()
    if not (source or medium) or is_direct_pair(source, medium):
        return None
    return source, medium


def _utm_result(source: str, medium: str) -> ChannelResult:
    def result(channel: Channel, platform: str = "") -> ChannelResult:
        return ChannelResult(channel, platform, ChannelBasis.UTM)

    paid = PAID_MEDIUM.match(medium) is not None
    if source in SEARCH_SOURCES and paid:
        return result(Channel.PAID_SEARCH, SEARCH_SOURCES[source])
    if source in _SOCIAL_AND_VIDEO_SOURCES and paid:
        return result(Channel.PAID_SOCIAL, _SOCIAL_AND_VIDEO_SOURCES[source])
    if medium in DISPLAY_MEDIA or paid:
        return result(Channel.OTHER)
    if source in SEARCH_SOURCES or medium == "organic":
        return result(Channel.ORGANIC_SEARCH, SEARCH_SOURCES.get(source, ""))
    if (
        source in _SOCIAL_AND_VIDEO_SOURCES
        or medium in SOCIAL_MEDIA
        or VIDEO_MEDIUM.match(medium)
    ):
        return result(Channel.ORGANIC_SOCIAL, _SOCIAL_AND_VIDEO_SOURCES.get(source, ""))
    if source in EMAIL_VALUES or medium in EMAIL_VALUES:
        return result(Channel.EMAIL, "Email")
    if medium in REFERRAL_MEDIA:
        return result(Channel.REFERRAL)
    return result(Channel.OTHER)


def _has_google_click_id(first_touch: FirstTouch) -> bool:
    return bool(first_touch.gclid or first_touch.gbraid or first_touch.wbraid)


def _referer_result(referer: str) -> ChannelResult | None:
    host = referer_host(referer)
    if not host:
        return None

    def result(channel: Channel, platform: str = "") -> ChannelResult:
        return ChannelResult(channel, platform, ChannelBasis.REFERER)

    # Checked on the raw string first: `referer_host` returns a bare package name,
    # which could otherwise match a web host table.
    if referer.strip().lower().startswith(_ANDROID_APP_PREFIX):
        channel, platform = APP_PACKAGES.get(host, (Channel.REFERRAL, ""))
        return result(channel, platform)
    mail_platform = _lookup(host, EMAIL_HOSTS)
    if mail_platform is not None:
        return result(Channel.EMAIL, mail_platform)
    if GOOGLE_SEARCH_HOST.match(host):
        return result(Channel.ORGANIC_SEARCH, "Google")
    for channel, table in (
        (Channel.ORGANIC_SEARCH, SEARCH_HOSTS),
        (Channel.ORGANIC_SOCIAL, SOCIAL_HOSTS),
        (Channel.ORGANIC_SOCIAL, VIDEO_HOSTS),
    ):
        listed_platform = _lookup(host, table)
        if listed_platform is not None:
            return result(channel, listed_platform)
    return result(Channel.REFERRAL)


def classify(first_touch: FirstTouch | None) -> ChannelResult:
    """The first matching rule wins."""
    if first_touch is None:
        return ChannelResult(Channel.UNKNOWN, "", ChannelBasis.NONE)
    utm_pair = _utm_signal(first_touch)
    if utm_pair is not None:
        return _utm_result(*utm_pair)
    if _has_google_click_id(first_touch):
        return ChannelResult(Channel.PAID_SEARCH, "Google", ChannelBasis.GCLID)
    from_referer = _referer_result(first_touch.referer)
    if from_referer is not None:
        return from_referer
    return ChannelResult(Channel.DIRECT, "", ChannelBasis.NONE)
