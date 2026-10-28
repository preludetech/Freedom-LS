"""Export resource for the user model."""

from __future__ import annotations

from allauth.account.models import EmailAddress
from import_export.fields import Field

from django.contrib.auth import get_user_model
from django.db.models import Exists, OuterRef, QuerySet

from freedom_ls.site_aware_models.admin_exports import (
    SiteAwareModelResource,
    SpreadsheetBooleanWidget,
)

from .models import User

USER_EXPORT_FIELDS = (
    "id",
    "email",
    "first_name",
    "last_name",
    "is_active",
    "is_staff",
    "email_verified",
    "created_at",
    "last_login",
)


class UserResource(SiteAwareModelResource):
    """One row per user, with nothing that could open an account.

    The model also carries the password hash, the superuser flag, groups and
    permissions, and a resource with no ``fields`` would write all of them, so
    the columns are an explicit whitelist.
    """

    WIDGETS_MAP = {
        **SiteAwareModelResource.WIDGETS_MAP,
        "BooleanField": SpreadsheetBooleanWidget,
    }
    # Annotated in filter_export, so the changelist query is unchanged and no
    # row costs a query.
    email_verified = Field(
        attribute="email_verified", widget=SpreadsheetBooleanWidget()
    )

    class Meta:
        model = get_user_model()
        fields = USER_EXPORT_FIELDS
        export_order = USER_EXPORT_FIELDS

    def filter_export(
        self, queryset: QuerySet[User], **kwargs: object
    ) -> QuerySet[User]:
        # Matched on the address, not only the user: allauth lets a user hold
        # several addresses, and only the one the account signs in with counts.
        verified = EmailAddress.objects.filter(
            user=OuterRef("pk"), verified=True, email__iexact=OuterRef("email")
        )
        return queryset.annotate(email_verified=Exists(verified))
