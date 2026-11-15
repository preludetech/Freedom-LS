"""Reduce a host or a raw `Referer` header value to one comparable form.

Read-side only: the stored referer stays raw, and these helpers are applied when
comparing or grouping it.
"""

from urllib.parse import urlsplit

_WWW_PREFIX = "www."
_WEB_SCHEMES = frozenset({"http", "https"})
_ANDROID_APP_SCHEME = "android-app"


def normalised_host(host: str) -> str:
    """Reduce a bare host (a `request.get_host()` value, a `Site.domain` or a
    `urlsplit(...).hostname`) to one comparable form, so that `www.google.com`,
    `google.com.` and `google.com:443` all compare equal."""
    value = host.strip().lower()
    value = _without_port(value)
    # Trailing dots go first, so a lone `www.` has become `www` and is kept.
    value = value.rstrip(".")
    return value.removeprefix(_WWW_PREFIX)


def _without_port(value: str) -> str:
    if value.startswith("["):
        # A bracketed IPv6 literal keeps its address; without a closing
        # bracket there is no address to extract, so the value is kept.
        close = value.find("]")
        return value[1:close] if close != -1 else value
    if value.count(":") == 1:
        return value.partition(":")[0]
    # Two or more colons with no brackets is a bare IPv6 literal, kept whole.
    return value


def referer_host(referer: str) -> str:
    """Return the comparable host of a raw `Referer` value, or "" when it has none.

    A referer cut short at the stored length cap still yields its host,
    because the host comes first."""
    try:
        parts = urlsplit(referer.strip())
        hostname = parts.hostname
    except ValueError:
        return ""
    # `.port` is never read: it raises on a non-numeric port, and `.hostname`
    # has already dropped the port, the userinfo and the IPv6 brackets.
    if not hostname:
        return ""
    if parts.scheme in _WEB_SCHEMES:
        return normalised_host(hostname)
    if parts.scheme == _ANDROID_APP_SCHEME:
        # The host of an android-app referer is the app's package name,
        # returned bare: no `www.` or port handling applies to it.
        return hostname.lower()
    return ""
