"""Form for the course pause resume page."""

from __future__ import annotations

from unfold.widgets import UnfoldAdminTextareaWidget

from django import forms

from freedom_ls.audit_log.models import REASON_LENGTH


class ResumeCourseForm(forms.Form):
    reason = forms.CharField(max_length=REASON_LENGTH, widget=UnfoldAdminTextareaWidget)
