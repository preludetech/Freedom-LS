"""Export resources for the referral-tracking models."""

from __future__ import annotations

from import_export.fields import Field
from import_export.widgets import ForeignKeyWidget

from django.contrib.auth import get_user_model
from django.db.models import QuerySet

from freedom_ls.referral_tracking.models import (
    AttributionTouch,
    Conversion,
    FirstTouchCount,
    ReferralCode,
    ReferralCodeHit,
    SignupAttribution,
)
from freedom_ls.site_aware_models.admin_exports import (
    IsoDateTimeWidget,
    SiteAwareModelResource,
)


class SignupAttributionResource(SiteAwareModelResource):
    # The user's email, not the pk, so the sheet reads without a join.
    user = Field(attribute="user", widget=ForeignKeyWidget(get_user_model(), "email"))

    class Meta:
        model = SignupAttribution


class FirstTouchCountResource(SiteAwareModelResource):
    class Meta:
        model = FirstTouchCount


class ReferralCodeResource(SiteAwareModelResource):
    class Meta:
        model = ReferralCode


class ReferralCodeHitResource(SiteAwareModelResource):
    # The code text, not the pk, so the sheet reads without a join.
    referral_code = Field(
        attribute="referral_code", widget=ForeignKeyWidget(ReferralCode, "code")
    )

    class Meta:
        model = ReferralCodeHit


class AttributionTouchResource(SiteAwareModelResource):
    # The user's email, not the pk, so the sheet reads without a join.
    user = Field(attribute="user", widget=ForeignKeyWidget(get_user_model(), "email"))

    class Meta:
        model = AttributionTouch


class ConversionResource(SiteAwareModelResource):
    user = Field(attribute="user", widget=ForeignKeyWidget(get_user_model(), "email"))
    first_touch__occurred_at = Field(
        attribute="first_touch__occurred_at", widget=IsoDateTimeWidget()
    )
    last_touch__occurred_at = Field(
        attribute="last_touch__occurred_at", widget=IsoDateTimeWidget()
    )

    class Meta:
        model = Conversion
        fields = (
            "id",
            "user",
            "kind",
            "target_label",
            "occurred_at",
            "first_referral_code",
            "first_touch__occurred_at",
            "last_referral_code",
            "last_touch__occurred_at",
            "window_days",
        )
        export_order = fields

    def filter_export(
        self, queryset: QuerySet[Conversion], **kwargs: object
    ) -> QuerySet[Conversion]:
        return queryset.select_related("user", "first_touch", "last_touch")
