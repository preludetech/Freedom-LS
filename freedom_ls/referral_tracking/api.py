"""Read-only API resources for referral tracking.

Every viewset starts from the model's base manager: the default manager reads
the thread-local request site, and the base viewset's filter_queryset binds
every lookup to the key's site instead, so no lookup depends on thread state.
"""

from django.db.models import QuerySet
from rest_framework import serializers

from freedom_ls.api.routers import router
from freedom_ls.api.scopes import ApiScope
from freedom_ls.api.viewsets import ReadOnlyApiViewSet

from .models import ReferralCode


class ReferralCodeApiSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReferralCode
        fields = (
            "id",
            "code",
            "label",
            "notes",
            "destination",
            "inactive_destination",
            "is_active",
            "hit_count",
            "last_hit_at",
            "created_at",
        )
        read_only_fields = fields


class ReferralCodeApiViewSet(ReadOnlyApiViewSet):
    cursor_field = "created_at"
    required_scope = ApiScope.REFERRAL_DATA
    serializer_class = ReferralCodeApiSerializer

    def get_queryset(self) -> QuerySet[ReferralCode]:
        # Base manager: the base viewset binds the site (see the module docstring).
        return ReferralCode._base_manager.all()


router.register("referral-codes", ReferralCodeApiViewSet, basename="referral_code")
