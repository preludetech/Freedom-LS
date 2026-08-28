"""Admin form for CourseInterest."""

from __future__ import annotations

from freedom_ls.site_aware_models.forms import ConstraintValidationFormMixin

from .models import CourseInterest


class CourseInterestAdminForm(ConstraintValidationFormMixin):
    """Admin form for CourseInterest.

    ``site`` is un-excluded from validation so unique_course_interest is
    checked while cleaning rather than failing at the database. It is still
    never rendered.
    """

    class Meta:
        model = CourseInterest
        exclude = ["site"]
