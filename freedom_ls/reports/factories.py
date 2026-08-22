import factory

from freedom_ls.learner_management.factories import CohortFactory
from freedom_ls.reports.models import GeneratedReport
from freedom_ls.site_aware_models.factories import SiteAwareFactory


class GeneratedReportFactory(SiteAwareFactory):
    class Meta:
        model = GeneratedReport

    cohort = factory.SubFactory(CohortFactory)
    status = GeneratedReport.STATUS_PENDING
    # `file` is deliberately never set here — it is blank=True, and a default
    # value would write to storage on every test that builds a report.
