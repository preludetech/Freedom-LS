from django.db import models
from system_base.models import SiteAwareModel
from django.utils.translation import gettext_lazy as _


class Student(SiteAwareModel):
    """A student is a human, but they can't log in here"""

    short_name = models.CharField(max_length=150, blank=True, null=True)
    full_name = models.CharField(max_length=150, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    id_number = models.CharField(max_length=50, blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    cellphone = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return self.full_name or self.email or f"Student {self.pk}"


class Cohort(SiteAwareModel):
    name = models.CharField(_("name"), max_length=150)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["site_id", "name"], name="unique_cohort_name_per_site"
            )
        ]

    def __str__(self):
        return self.name


class CohortMembership(SiteAwareModel):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    cohort = models.ForeignKey(Cohort, on_delete=models.CASCADE)
