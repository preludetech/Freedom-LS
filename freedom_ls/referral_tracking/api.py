"""Read-only API resources for referral tracking.

Every viewset starts from the model's base manager: the default manager reads
the thread-local request site, and the base viewset's filter_queryset binds
every lookup to the key's site instead, so no lookup depends on thread state.
"""

import django_filters

from django.db.models import QuerySet
from rest_framework import serializers

from freedom_ls.api.filters import (
    AwareIsoDateTimeFilter,
    IsoDateFilter,
    UpdatedSinceFilterSet,
)
from freedom_ls.api.routers import router
from freedom_ls.api.scopes import ApiScope
from freedom_ls.api.viewsets import ReadOnlyApiViewSet

from .models import FirstTouchCount, ReferralCode, ReferralCodeHit, SignupAttribution


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


class ReferralCodeHitApiSerializer(serializers.ModelSerializer):
    referral_code_text = serializers.CharField(
        source="referral_code.code", read_only=True
    )

    class Meta:
        model = ReferralCodeHit
        fields = (
            "id",
            "referral_code",
            "referral_code_text",
            "door",
            "is_machine_fetch",
            "hit_at",
        )
        read_only_fields = fields


class ReferralCodeHitFilterSet(UpdatedSinceFilterSet):
    # Hits have no updated_at; hit_at is the instant a hit row can be filtered on.
    updated_since = AwareIsoDateTimeFilter(
        field_name="hit_at",
        lookup_expr="gte",
        help_text="Hits whose hit_at is at or after this instant.",
    )

    class Meta:
        model = ReferralCodeHit
        fields: list[str] = []


class ReferralCodeHitApiViewSet(ReadOnlyApiViewSet):
    cursor_field = "hit_at"
    filterset_class = ReferralCodeHitFilterSet
    required_scope = ApiScope.REFERRAL_DATA
    serializer_class = ReferralCodeHitApiSerializer

    def get_queryset(self) -> QuerySet[ReferralCodeHit]:
        # Base manager: the base viewset binds the site (see the module docstring).
        return ReferralCodeHit._base_manager.select_related("referral_code")


router.register(
    "referral-code-hits", ReferralCodeHitApiViewSet, basename="referral_code_hit"
)


class SignupAttributionApiSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = SignupAttribution
        # client_ip, user_agent, ga_cookie, fbp_cookie and fbc_cookie are
        # withheld: they stay behind the admin's view permission and export.
        fields = (
            "id",
            "user",
            "user_email",
            "advert_code",
            "referral_code",
            "utm_source",
            "utm_medium",
            "utm_campaign",
            "utm_content",
            "utm_term",
            "gclid",
            "gbraid",
            "wbraid",
            "fbclid",
            "landing_path",
            "referer",
            "raw_query",
            "first_seen",
            "signed_up_at",
        )
        read_only_fields = fields


class SignupAttributionFilterSet(UpdatedSinceFilterSet):
    # Attributions are append-only; signed_up_at is the instant a row can be filtered on.
    updated_since = AwareIsoDateTimeFilter(
        field_name="signed_up_at",
        lookup_expr="gte",
        help_text="Signup attributions whose signed_up_at is at or after this instant.",
    )

    class Meta:
        model = SignupAttribution
        fields: list[str] = []


class SignupAttributionApiViewSet(ReadOnlyApiViewSet):
    cursor_field = "signed_up_at"
    filterset_class = SignupAttributionFilterSet
    required_scope = ApiScope.REFERRAL_DATA
    serializer_class = SignupAttributionApiSerializer

    def get_queryset(self) -> QuerySet[SignupAttribution]:
        # Base manager: the base viewset binds the site (see the module docstring).
        return SignupAttribution._base_manager.select_related("user")


router.register(
    "signup-attributions", SignupAttributionApiViewSet, basename="signup_attribution"
)


class FirstTouchCountApiSerializer(serializers.ModelSerializer):
    class Meta:
        model = FirstTouchCount
        fields = (
            "id",
            "day",
            "advert_code",
            "referral_code",
            "utm_source",
            "utm_medium",
            "utm_campaign",
            "utm_content",
            "utm_term",
            "is_overflow",
            "key_hash",
            "count",
        )
        read_only_fields = fields


class FirstTouchCountFilterSet(django_filters.FilterSet):
    # A count changes in place with no timestamp, so the filter is named for
    # the day it compares against rather than claiming a change signal.
    day_since = IsoDateFilter(
        field_name="day",
        lookup_expr="gte",
        help_text="Counts whose day is on or after this date, as YYYY-MM-DD.",
    )

    class Meta:
        model = FirstTouchCount
        fields: list[str] = []


class FirstTouchCountApiViewSet(ReadOnlyApiViewSet):
    cursor_field = "day"
    filterset_class = FirstTouchCountFilterSet
    required_scope = ApiScope.REFERRAL_DATA
    serializer_class = FirstTouchCountApiSerializer

    def get_queryset(self) -> QuerySet[FirstTouchCount]:
        # Base manager: the base viewset binds the site (see the module docstring).
        return FirstTouchCount._base_manager.all()


router.register(
    "first-touch-counts", FirstTouchCountApiViewSet, basename="first_touch_count"
)
