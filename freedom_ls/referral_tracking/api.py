"""Read-only API resources for referral tracking.

Every viewset starts from the model's base manager: the default manager reads
the thread-local request site, and the base viewset's filter_queryset binds
every lookup to the key's site instead, so no lookup depends on thread state.
"""

import django_filters

from rest_framework import serializers

from freedom_ls.api.filters import AwareIsoDateTimeFilter, IsoDateFilter
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
    queryset = ReferralCode._base_manager.all()
    cursor_field = "created_at"
    required_scope = ApiScope.REFERRAL_DATA
    serializer_class = ReferralCodeApiSerializer


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


class ReferralCodeHitFilterSet(django_filters.FilterSet):
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
    queryset = ReferralCodeHit._base_manager.select_related("referral_code")
    cursor_field = "hit_at"
    filterset_class = ReferralCodeHitFilterSet
    required_scope = ApiScope.REFERRAL_DATA
    serializer_class = ReferralCodeHitApiSerializer


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


class SignupAttributionFilterSet(django_filters.FilterSet):
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
    queryset = SignupAttribution._base_manager.select_related("user")
    cursor_field = "signed_up_at"
    filterset_class = SignupAttributionFilterSet
    required_scope = ApiScope.REFERRAL_DATA
    serializer_class = SignupAttributionApiSerializer


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
    queryset = FirstTouchCount._base_manager.all()
    cursor_field = "day"
    filterset_class = FirstTouchCountFilterSet
    required_scope = ApiScope.REFERRAL_DATA
    serializer_class = FirstTouchCountApiSerializer


router.register(
    "first-touch-counts", FirstTouchCountApiViewSet, basename="first_touch_count"
)
