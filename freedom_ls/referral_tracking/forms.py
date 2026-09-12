"""Admin form for ReferralCode."""

from __future__ import annotations

from django import forms

from freedom_ls.referral_tracking.codes import lookup_referral_code
from freedom_ls.referral_tracking.models import ReferralCode
from freedom_ls.site_aware_models.forms import ConstraintValidationFormMixin


class ReferralCodeForm(ConstraintValidationFormMixin):
    """Admin form for ReferralCode.

    `code` is made optional here rather than on the model: a blank value
    is valid on the add form because `ReferralCode.full_clean()` generates
    one, but the field itself is still required once a code exists. The
    mixin's default `constraint_fields` is `("site",)`, which is what
    `unique_referral_code_per_site` needs, so a case-only duplicate reaches
    form validation rather than an `IntegrityError`. Left to the mixin
    alone, though, that constraint failure surfaces as a non-field error
    naming the database constraint, so `clean_code` below checks for a
    duplicate itself and attaches a plain-English error to `code` before the
    constraint ever gets a chance to fire.
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

    def clean_code(self) -> str:
        code: str = self.cleaned_data.get("code", "")
        if not code:
            return code
        # A blank code is filled in by ReferralCode.full_clean(), which also
        # sets `site` from the current request. Do that here too, so the
        # lookup below is scoped to the right site before that later step runs.
        self.instance._set_site_from_request()
        if not self.instance.site_id:
            return code
        existing = lookup_referral_code(self.instance.site, code)
        if existing is not None and existing.pk != self.instance.pk:
            raise forms.ValidationError(
                "This code is already in use. Choose a different one."
            )
        return code
