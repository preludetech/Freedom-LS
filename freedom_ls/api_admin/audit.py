from __future__ import annotations

from freedom_ls.api.models import ApiKey
from freedom_ls.audit_log.types import JSONValue


def key_details(api_key: ApiKey) -> dict[str, JSONValue]:
    return {
        "name": api_key.name,
        "key_prefix": api_key.key_prefix,
        "scopes": list(api_key.scopes),
        "expires_at": api_key.expires_at.isoformat() if api_key.expires_at else None,
    }
