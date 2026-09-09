"""Export resources for the two referral-tracking models."""

from __future__ import annotations

from import_export.fields import Field
from import_export.widgets import ForeignKeyWidget

from django.contrib.auth import get_user_model

from freedom_ls.referral_tracking.models import FirstTouchCount, SignupAttribution
from freedom_ls.site_aware_models.admin_exports import SiteAwareModelResource


class SignupAttributionResource(SiteAwareModelResource):
    # The user's email, not the pk, so the sheet reads without a join.
    user = Field(attribute="user", widget=ForeignKeyWidget(get_user_model(), "email"))

    class Meta:
        model = SignupAttribution


class FirstTouchCountResource(SiteAwareModelResource):
    class Meta:
        model = FirstTouchCount
