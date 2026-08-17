from __future__ import annotations

from unfold.widgets import UnfoldAdminSelectWidget

from django import forms
from django.db.models import QuerySet

from freedom_ls.student_management.models import Cohort


class GenerateReportForm(forms.Form):
    """Cohort picker for the admin's "Generate cohort report" page.

    The queryset is supplied per request: it is the guardian-filtered set of
    cohorts the user may view, and it is what stops a tampered POST from
    reaching a cohort the user cannot see.
    """

    def __init__(self, *args, cohorts: QuerySet[Cohort], **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fields["cohort"] = forms.ModelChoiceField(
            queryset=cohorts,
            widget=UnfoldAdminSelectWidget,
            empty_label=None,
            label="Cohort",
        )
