"""Reporting surfaces of the educator interface: files built from a cohort's people."""

from __future__ import annotations

import csv
import io
from typing import cast

from django.http import HttpResponse
from django.utils import timezone
from django.utils.http import content_disposition_header
from django.utils.text import slugify

from freedom_ls.base.csv_safety import UTF8_BOM, escape_csv_formula
from freedom_ls.learner_management.models import Cohort
from freedom_ls.learner_management.queries import cohort_educators, learner_status
from freedom_ls.reports.indexes import learner_sort_key, load_active_memberships


def cohort_members_csv_response(cohort: Cohort) -> HttpResponse:
    """The cohort's active learners, then its educators, as one formula-safe CSV.

    The body is built in memory rather than streamed: a streamed body is read
    after the site thread-local is cleared, and a cohort's membership list is
    small. learner_status reads only the loaded User row, so no query runs
    per row.
    """
    learners = sorted(
        (
            membership.learner
            for membership in load_active_memberships(cohort, cohort.site_id)
        ),
        key=lambda learner: learner_sort_key(learner.user),
    )
    buffer = io.StringIO()
    buffer.write(UTF8_BOM)
    writer = csv.writer(buffer)
    writer.writerow(["Name", "Email", "Role", "Status"])
    for learner in learners:
        writer.writerow(
            [
                escape_csv_formula(learner.user.display_name),
                escape_csv_formula(learner.user.email),
                "Learner",  # a label for the reader, not a permission role
                learner_status(learner).label,
            ]
        )
    for user, role_display_name in cohort_educators(cohort):
        writer.writerow(
            [
                escape_csv_formula(user.display_name),
                escape_csv_formula(user.email),
                escape_csv_formula(role_display_name),
                "",
            ]
        )
    response = HttpResponse(buffer.getvalue(), content_type="text/csv; charset=utf-8")
    # With a filename the header is always produced; None is only returned
    # when both as_attachment and filename are falsy.
    response["Content-Disposition"] = cast(
        str,
        content_disposition_header(
            as_attachment=True, filename=_members_csv_filename(cohort)
        ),
    )
    return response


def _members_csv_filename(cohort: Cohort) -> str:
    organisation = slugify(cohort.organisation.name, allow_unicode=True)
    name = slugify(cohort.name, allow_unicode=True)
    return f"{organisation}-{name}-members-{timezone.localdate():%Y-%m-%d}.csv"
