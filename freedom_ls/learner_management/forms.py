"""Admin forms for learner_management models.

SiteAwareModelAdmin excludes ``site`` from every admin form, and
UniqueConstraint.validate() abandons a constraint whose field sits in that
exclusion set. Each model here carries a site-scoped UniqueConstraint, so
each gets a ConstraintValidationFormMixin form.
"""

from __future__ import annotations

from freedom_ls.site_aware_models.forms import ConstraintValidationFormMixin

from .models import (
    Cohort,
    CohortCourseRegistration,
    Learner,
    LearnerCourseRegistration,
)


class CohortAdminForm(ConstraintValidationFormMixin):
    """Admin form for Cohort.

    ``site`` is un-excluded from validation so
    unique_cohort_name_per_organisation is checked while cleaning rather than
    failing at the database. It is still never rendered.
    """

    class Meta:
        model = Cohort
        exclude = ["site"]


class LearnerAdminForm(ConstraintValidationFormMixin):
    """Admin form for Learner.

    ``site`` is un-excluded from validation so
    unique_learner_per_organisation is checked while cleaning rather than
    failing at the database. It is still never rendered.
    """

    class Meta:
        model = Learner
        exclude = ["site"]


class LearnerCourseRegistrationAdminForm(ConstraintValidationFormMixin):
    """Admin form for LearnerCourseRegistration.

    ``site`` is un-excluded from validation so
    unique_learner_course_registration is checked while cleaning rather than
    failing at the database. It is still never rendered.
    """

    class Meta:
        model = LearnerCourseRegistration
        exclude = ["site"]


class CohortCourseRegistrationAdminForm(ConstraintValidationFormMixin):
    """Admin form for CohortCourseRegistration.

    ``site`` is un-excluded from validation so
    unique_cohort_course_registration is checked while cleaning rather than
    failing at the database. It is still never rendered.
    """

    class Meta:
        model = CohortCourseRegistration
        exclude = ["site"]
