"""Per-client-address request caps."""

from __future__ import annotations

import sentry_sdk

from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError
from django.http import HttpRequest
from django.utils import timezone
from django.utils.crypto import salted_hmac

from freedom_ls.accounts.utils import get_client_ip


def is_ip_throttled(
    request: HttpRequest,
    *,
    namespace: str,
    scope: str,
    limit: int,
    window_seconds: int,
) -> bool:
    """Fixed-window per-IP counter.

    limit or window <= 0 disables. PermissionDenied from get_client_ip
    propagates: a missing proxy header means the edge was bypassed, and the
    caller decides whether that refuses the request. A cache backend failure
    (a database error from the database cache, a socket error from a cache
    server) reports to Sentry and returns False: a broken cache costs the cap,
    not the request.
    """
    if limit <= 0 or window_seconds <= 0:
        return False
    ip = get_client_ip(request)
    if not ip:
        # No proxy header is configured and REMOTE_ADDR is empty: the client is
        # unknown, and creating rows for an unknown client is what the cap exists
        # to stop.
        raise PermissionDenied("Client address unknown.")
    # The key reaches storage, so the address must not be readable from it,
    # and the IPv4 space is small enough to exhaust a plain digest: keyed on
    # SECRET_KEY through salted_hmac.
    fingerprint = salted_hmac(namespace, ip).hexdigest()[:32]
    # A key per window rather than one whose expiry is pushed out: on a
    # backend without a native incr, cache.incr is get-then-set and resets the
    # timeout, so a steady stream would keep one counter alive for good.
    bucket = int(timezone.now().timestamp()) // window_seconds
    key = f"{namespace}:{scope}:{fingerprint}:{bucket}"
    try:
        if cache.add(key, 1, window_seconds * 2):
            return False
        count = cache.incr(key)
    except ValueError:
        # The bucket expired between the add and the incr.
        return False
    except (DatabaseError, OSError) as exc:
        # The backend being down is the backend's problem: a cap must never
        # take the request down with it. Reported rather than swallowed. A
        # programming error still raises.
        sentry_sdk.capture_exception(exc)
        return False
    return bool(count > limit)
