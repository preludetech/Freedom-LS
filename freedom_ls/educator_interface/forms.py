from django import forms

from freedom_ls.content_engine.models import Course
from freedom_ls.student_management.models import Cohort


class CohortForm(forms.ModelForm):
    class Meta:
        model = Cohort
        fields = ["name"]


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ["title", "category", "visibility"]
