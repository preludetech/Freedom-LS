from __future__ import annotations

from unfold.widgets import UnfoldAdminSelectWidget

from django import forms
from django.db.models import QuerySet

from freedom_ls.learner_management.models import Cohort


class CohortChoiceField(forms.ModelChoiceField):
    """Labels each cohort with its organisation.

    Cohort names are unique per organisation, not per site, so two cohorts on
    one site may legitimately share a name. Cohort.__str__ stays the bare name
    -- everywhere else it is read, the educator interface, an organisation is
    already established by the URL.
    """

    def label_from_instance(self, obj: Cohort) -> str:
        return f"{obj.organisation.name} \u2014 {obj.name}"


class GenerateReportForm(forms.Form):
    """Cohort picker for the admin's "Generate cohort report" page.

    The queryset is supplied per request: it is the guardian-filtered set of
    cohorts the user may view, and it is what stops a tampered POST from
    reaching a cohort the user cannot see.
    """

    def __init__(self, *args, cohorts: QuerySet[Cohort], **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fields["cohort"] = CohortChoiceField(
            queryset=cohorts,
            widget=UnfoldAdminSelectWidget,
            empty_label=None,
            label="Cohort",
        )
