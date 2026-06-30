from django import forms

from freedom_ls.student_management.models import Cohort


class CohortForm(forms.ModelForm):
    class Meta:
        model = Cohort
        fields = ["name"]
