from health_check.views import HealthCheckView

from django.http import HttpRequest, JsonResponse
from django.views.decorators.cache import never_cache

from freedom_ls.health.config import config


@never_cache
def liveness(request: HttpRequest) -> JsonResponse:
    """Shallow liveness probe. Returns 200 whenever the process can serve a
    request; touches no database, cache, or other dependency by design.
    never_cache so an intermediary can't serve a stale 200 for a process that
    can no longer respond."""
    return JsonResponse({"status": "alive"})


class ReadinessView(HealthCheckView):
    """Readiness probe: runs the FLS default check set (DB-only unless a project
    overrides HEALTH_READINESS_CHECKS). Non-200 when a checked dependency is down."""

    @property
    def checks(self) -> list[str]:
        return config.HEALTH_READINESS_CHECKS
