"""Forms for the course progress pause and resume pages."""

from __future__ import annotations

from django import forms

from freedom_ls.audit_log.models import REASON_LENGTH


class ReasonForm(forms.Form):
    reason = forms.CharField(max_length=REASON_LENGTH, widget=forms.Textarea)


class PauseCourseForm(ReasonForm):
    planned_resume_on = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text=(
            "Leave empty to pause until you resume it. Deadlines move by the whole "
            "days paused, rounded up."
        ),
    )


class ResumeCourseForm(ReasonForm):
    pass
