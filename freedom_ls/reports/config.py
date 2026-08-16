from __future__ import annotations

from freedom_ls.base.app_settings import AppSettings, Setting


class ReportsConfig(AppSettings):
    REPORTS_STORAGE_ALIAS: str
    REPORTS_AT_RISK_RULES_MODULE: str
    REPORTS_MAX_STUDENTS: int
    REPORTS_MAX_QUIZ_COLUMNS: int

    declared_settings = {
        "REPORTS_STORAGE_ALIAS": Setting(default="reports"),
        "REPORTS_AT_RISK_RULES_MODULE": Setting(
            default="freedom_ls.reports.at_risk.rules"
        ),
        # A resource guard, not a product rule: the safe ceiling depends on the
        # deployment's worker memory and render budget, which FLS cannot know.
        "REPORTS_MAX_STUDENTS": Setting(default=500),
        # A layout budget, not a product rule: 11 quiz columns (14 columns in
        # all) is the largest a summary table renders without clipping on A4
        # landscape, measured on real rendered pages. A deployment that changes
        # the page size, font or Completion column width can raise or lower it.
        "REPORTS_MAX_QUIZ_COLUMNS": Setting(default=11),
    }


config = ReportsConfig()
