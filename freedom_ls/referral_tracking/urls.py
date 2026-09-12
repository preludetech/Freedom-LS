"""The `/go/{code}` and `/d/{CODE}` referral redirect routes.

Case is spelled as character classes, not an inline `(?i:...)` flag: Django's
`path()` enforces neither the case-insensitivity nor `CODE_PATTERN`, and an
inline flag makes `reverse()` raise `ValueError: Non-reversible reg-exp
portion`.
"""

from __future__ import annotations

from django.urls import re_path

from freedom_ls.referral_tracking.codes import CODE_PATTERN
from freedom_ls.referral_tracking.models import Door
from freedom_ls.referral_tracking.views import follow_referral_code

app_name = "referral_tracking"

urlpatterns = [
    re_path(
        rf"^[gG][oO]/(?P<code>{CODE_PATTERN.pattern})$",
        follow_referral_code,
        {"door": Door.GO},
        name="follow_go",
    ),
    re_path(
        rf"^[dD]/(?P<code>{CODE_PATTERN.pattern})$",
        follow_referral_code,
        {"door": Door.D},
        name="follow_d",
    ),
]
