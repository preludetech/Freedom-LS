"""Admin form for RecommendedCourse."""

from __future__ import annotations

from freedom_ls.course_recommendations.models import RecommendedCourse
from freedom_ls.site_aware_models.forms import ConstraintValidationFormMixin


class RecommendedCourseAdminForm(ConstraintValidationFormMixin):
    """site is un-excluded from validation so unique_recommended_course is checked
    while cleaning rather than failing at the database. It is still never rendered."""

    class Meta:
        model = RecommendedCourse
        exclude = ["site"]
