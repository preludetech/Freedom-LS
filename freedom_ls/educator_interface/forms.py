from freedom_ls.site_aware_models.forms import SiteScopedConstraintFormMixin
from freedom_ls.student_management.models import Cohort


class CohortForm(SiteScopedConstraintFormMixin):
    """Form for a cohort's editable fields.

    ``organisation`` is un-excluded so ``unique_cohort_name_per_site`` is
    checked while cleaning rather than failing at the database. ``site`` is
    left excluded: the constraint names it by attname (``site_id``), which
    never matches the field name Django puts in the exclusion set, so the
    constraint already sees it. Un-excluding it would only add the site field
    to the model's own field validation, where an error could not be attached
    to any form field.
    """

    constraint_fields = ("organisation",)

    class Meta:
        model = Cohort
        fields = ["name"]
