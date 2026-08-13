import factory

from freedom_ls.reports.models import GeneratedReport
from freedom_ls.site_aware_models.factories import SiteAwareFactory
from freedom_ls.student_management.factories import CohortFactory


class GeneratedReportFactory(SiteAwareFactory):
    class Meta:
        model = GeneratedReport

    cohort = factory.SubFactory(CohortFactory)
    status = GeneratedReport.STATUS_PENDING
    # `file` is deliberately never set here — it is blank=True, and a default
    # value would write to storage on every test that builds a report.
