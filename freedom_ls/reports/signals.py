"""Signal receivers for the reports app.

Connected by `ReportsConfig.ready()`. A receiver in a module nothing imports
is never connected, and fails silently rather than loudly.
"""

from __future__ import annotations

from django.db.models.signals import post_delete
from django.dispatch import receiver

from freedom_ls.reports.models import GeneratedReport


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
