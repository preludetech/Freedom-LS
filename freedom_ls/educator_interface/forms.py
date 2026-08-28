from freedom_ls.learner_management.models import Cohort
from freedom_ls.site_aware_models.forms import ConstraintValidationFormMixin


class CohortForm(ConstraintValidationFormMixin):
    """Form for a cohort's editable fields.

    ``organisation`` and ``site`` are both un-excluded so
    ``unique_cohort_name_per_organisation`` is checked while cleaning rather
    than failing at the database. Un-excluding ``site`` is safe even though
    neither it nor ``organisation`` is rendered here: SiteAwareModelBase.full_clean()
    fills ``site`` from the current request before validation runs, and the
    view attaches ``organisation`` to the instance before the form validates.
    """

    constraint_fields = ("organisation", "site")

    class Meta:
        model = Cohort
        fields = ["name"]
