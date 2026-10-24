"""Signal receivers for the reports app.

Connected by `ReportsConfig.ready()`. A receiver in a module nothing imports
is never connected, and fails silently rather than loudly.
"""

from __future__ import annotations

from django.db.models import Model
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from freedom_ls.learner_management.models import (
    CohortCourseRegistration,
    CohortMembership,
)
from freedom_ls.reports.models import GeneratedReport
from freedom_ls.reports.screen_cache import forget_cohort


@receiver(post_delete, sender=GeneratedReport)
def delete_report_file(
    sender: type[GeneratedReport], instance: GeneratedReport, **kwargs: object
) -> None:
    """Storage does not follow the row. An orphaned PDF is PII left behind.

    TODO: no retention/expiry policy exists yet for report files while their
    row is still alive — this only cleans up on delete. Do not remove this
    TODO without implementing retention.
    """
    if not instance.file:
        return
    instance.file.delete(save=False)


@receiver([post_save, post_delete], sender=CohortMembership)
@receiver([post_save, post_delete], sender=CohortCourseRegistration)
def forget_changed_cohort(
    sender: type[Model],
    instance: CohortMembership | CohortCourseRegistration,
    **kwargs: object,
) -> None:
    """A cached screen gather holds who is in the cohort and which courses it
    is registered for, so a change to either drops the cohort's entries.
    Progress writes are deliberately not watched: the cache is what keeps
    them off the hot path."""
    forget_cohort(instance.site_id, instance.cohort_id)
