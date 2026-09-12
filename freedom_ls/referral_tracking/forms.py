"""Admin form for ReferralCode."""

from __future__ import annotations

from freedom_ls.referral_tracking.models import ReferralCode
from freedom_ls.site_aware_models.forms import ConstraintValidationFormMixin


class ReferralCodeForm(ConstraintValidationFormMixin):
    """Admin form for ReferralCode.

    `code` is made optional here rather than on the model: a blank value
    is valid on the add form because `ReferralCode.full_clean()` generates
    one, but the field itself is still required once a code exists. The
    mixin's default `constraint_fields` is `("site",)`, which is what
    `unique_referral_code_per_site` needs, so a case-only duplicate is a
    form error rather than an `IntegrityError`.
    """

    class Meta:
        model = ReferralCode
        fields = [
            "code",
            "label",
            "notes",
            "destination",
            "inactive_destination",
            "is_active",
        ]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        code = self.fields.get("code")
        if code is not None:
            code.required = False
