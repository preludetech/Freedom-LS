from freedom_ls.learner_management.models import Cohort
from freedom_ls.site_aware_models.forms import ConstraintValidationFormMixin


class CohortForm(ConstraintValidationFormMixin):
    """Form for a cohort's editable fields.

    ``organisation`` is un-excluded so ``unique_cohort_name_per_site`` is
    checked while cleaning rather than failing at the database. ``site`` is
    left out: the constraint names it ``site_id``, which the exclusion set
    never matches, so the constraint already sees it. Un-excluding it would
    only add the site field to the model's own validation, where an error could
    not be attached to any form field.
    """

    constraint_fields = ("organisation",)

    class Meta:
        model = Cohort
        fields = ["name"]
