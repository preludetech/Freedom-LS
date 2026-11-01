from django.contrib import admin
from django.contrib.admin import ModelAdmin
from django.db.models import Q, QuerySet
from django.http import HttpRequest
from django.utils import timezone

from freedom_ls.api.models import ApiKey, ApiKeyStatus


class ApiKeyStatusFilter(admin.SimpleListFilter):
    title = "status"
    parameter_name = "status"

    def lookups(
        self, request: HttpRequest, model_admin: ModelAdmin
    ) -> list[tuple[str, str]]:
        return list(ApiKeyStatus.choices)

    def queryset(
        self, request: HttpRequest, queryset: QuerySet[ApiKey]
    ) -> QuerySet[ApiKey]:
        now = timezone.now()
        match self.value():
            case ApiKeyStatus.ACTIVE:
                return queryset.filter(revoked_at__isnull=True).filter(
                    Q(expires_at__isnull=True) | Q(expires_at__gt=now)
                )
            case ApiKeyStatus.EXPIRED:
                return queryset.filter(revoked_at__isnull=True, expires_at__lte=now)
            case ApiKeyStatus.REVOKED:
                return queryset.filter(revoked_at__isnull=False)
        return queryset
