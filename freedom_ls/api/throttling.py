from __future__ import annotations

from rest_framework.request import Request
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from .config import config
from .models import ApiKey


class ApiKeyRateThrottle(SimpleRateThrottle):
    scope = "api_key"

    def get_rate(self) -> str:
        # DRF's own get_rate reads a REST_FRAMEWORK setting this project does not define.
        return str(config.API_THROTTLE_RATE)

    def get_cache_key(self, request: Request, view: APIView) -> str | None:
        api_key = request.auth
        if not isinstance(api_key, ApiKey):
            return None
        # The pk, never the key text or its hash, so the cache holds no secret material.
        cache_key: str = self.cache_format % {
            "scope": self.scope,
            "ident": str(api_key.pk),
        }
        return cache_key
