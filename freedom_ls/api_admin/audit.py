from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest

from freedom_ls.api.models import ApiKey
from freedom_ls.audit_log.types import JSONValue

if TYPE_CHECKING:
    from freedom_ls.accounts.models import User


def key_details(api_key: ApiKey) -> dict[str, JSONValue]:
    return {
        "name": api_key.name,
        "key_prefix": api_key.key_prefix,
        "scopes": list(api_key.scopes),
        "expires_at": api_key.expires_at.isoformat() if api_key.expires_at else None,
    }


def acting_user(request: HttpRequest) -> User:
    """The signed-in user making an admin request, as the audit log's actor."""
    actor = request.user
    if not isinstance(actor, get_user_model()):
        raise PermissionDenied("Only a signed-in user can manage a key.")
    return actor
