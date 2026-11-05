# ruff: noqa: T201 -- a manage.py shell script whose output is printed for the QA operator

from django.contrib.sites.models import Site
from django.utils import timezone

from freedom_ls.accounts.models import User
from freedom_ls.learner_management.models import (
    ImportLabel,
    ImportStatus,
    LearnerImport,
    LearnerImportRow,
)
from freedom_ls.organisations.models import Organisation

site = Site.objects.get(name="DemoDev")
org = Organisation._base_manager.get(slug="demodev", site=site)
user = User._base_manager.get(email="demodev@email.com", site=site)
ROWS, DONE = 300, 120
now = timezone.now()
li = LearnerImport.objects.create(
    site=site,
    organisation=org,
    cohort=None,
    requested_by=user,
    file_name="qa-in-progress-300.csv",
    status=ImportStatus.RUNNING,
    row_count=ROWS,
    processed_count=DONE,
    started_at=now,
)
LearnerImportRow.objects.bulk_create(
    [
        LearnerImportRow(
            site=site,
            learner_import=li,
            line_number=n + 2,
            email=f"qa_import_progress_{n + 1:03d}@email.com",
            first_name="QA",
            last_name=f"Import {n + 1:03d}",
            preview_label=ImportLabel.NEW_ACCOUNT,
            final_label=ImportLabel.NEW_ACCOUNT if n < DONE else None,
        )
        for n in range(ROWS)
    ]
)
li.refresh_from_db()
print(
    "PK",
    li.pk,
    str(li),
    li.site_id,
    li.row_count,
    li.processed_count,
    li.started_at,
    li.finished_at,
)
print("rows", li.rows.count(), "final", li.rows.exclude(final_label=None).count())
print(f"/educator/organisations/{org.slug}/learners/import/{li.pk}/result/")
