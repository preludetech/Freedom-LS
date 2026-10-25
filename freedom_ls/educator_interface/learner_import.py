"""Importing learners from a CSV file: parse and label the rows for a preview,
then commit them. Preview and commit classify each row through the same
steps, so what the preview promised is what the commit does unless the data
changed in between."""

from __future__ import annotations

import os
from collections import defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import cast

from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404

from freedom_ls.accounts.models import User
from freedom_ls.base.csv_import import LINE_KEY, parse_csv
from freedom_ls.learner_management.capabilities import can
from freedom_ls.learner_management.config import config
from freedom_ls.learner_management.learner_actions import (
    AddLearnerResult,
    AddOutcome,
    CohortOutcome,
    ImportLookup,
    LearnerEntry,
    add_learner,
    classify_learner_entry,
)
from freedom_ls.learner_management.models import (
    Cohort,
    ImportLabel,
    ImportStatus,
    LearnerImport,
    LearnerImportRow,
    RunStatus,
)
from freedom_ls.learner_management.queries import (
    ADD_COHORTMEMBERSHIP,
    ADD_LEARNER,
    BULK_MANAGE_LEARNERS,
    cohorts_visible_to,
)
from freedom_ls.learner_management.run_records import record_run
from freedom_ls.organisations.models import Organisation

HEADERS = ("email", "first_name", "last_name", "cohort")
EMAIL_MAX_LENGTH = 254
NAME_MAX_LENGTH = 150
#: Zero-width and non-breaking spaces survive `str.strip` and arrive in
#: addresses copied from web pages and documents.
EMAIL_NOISE = ("​", "﻿", "\xa0")

INVALID_EMAIL_REASON = "This isn't a valid email address."
OTHER_SITE_REASON = "This address belongs to an account on another site."
COHORT_UNAVAILABLE_REASON = "That cohort can no longer take learners."
PERMISSION_LOST_MESSAGE = "You no longer have permission to import learners here."

#: The label shown for each (AddOutcome, CohortOutcome) pair of a row that
#: can be added. An outcome with no cohort behaves as "already a member".
LABEL_FOR: dict[tuple[AddOutcome, CohortOutcome | None], ImportLabel] = {
    **{
        (AddOutcome.CREATED, cohort): ImportLabel.NEW_ACCOUNT
        for cohort in (None, *CohortOutcome)
    },
    **{
        (AddOutcome.JOINED, cohort): ImportLabel.JOINED
        for cohort in (None, *CohortOutcome)
    },
    **{
        (AddOutcome.REACTIVATED, cohort): ImportLabel.REACTIVATED
        for cohort in (None, *CohortOutcome)
    },
    (AddOutcome.ALREADY_LEARNER, CohortOutcome.ADDED): ImportLabel.ADDED_TO_COHORT,
    (AddOutcome.ALREADY_LEARNER, CohortOutcome.ALREADY_MEMBER): (
        ImportLabel.ALREADY_MEMBER
    ),
    (AddOutcome.ALREADY_LEARNER, None): ImportLabel.ALREADY_MEMBER,
}

#: Labels that write nothing, so they do not count towards "Add N learners".
NOT_ADDED_LABELS = (ImportLabel.ERROR, ImportLabel.ALREADY_MEMBER)


def check_import_gate(
    user: User, organisation: Organisation, cohort: Cohort | None
) -> bool:
    """Whether `user` may import learners: into the organisation from the
    learners list, or into one active cohort from its page."""
    if cohort is None:
        return can(user, BULK_MANAGE_LEARNERS, organisation) and can(
            user, ADD_LEARNER, organisation
        )
    return (
        cohort.is_active
        and can(user, ADD_LEARNER, organisation)
        and can(user, ADD_COHORTMEMBERSHIP, cohort)
    )


def create_learner_import(
    user: User,
    organisation: Organisation,
    cohort: Cohort | None,
    uploaded_file: UploadedFile,
) -> LearnerImport:
    """Parse the file and store it as a previewed import with every row
    labelled. Raises `CsvImportError` for a file that cannot be read, storing
    nothing."""
    rows = parse_csv(
        uploaded_file,
        accepted_headers=HEADERS,
        required_headers=("email",),
        max_rows=config.LEARNER_IMPORT_MAX_ROWS,
    )
    with transaction.atomic():
        learner_import = cast(
            LearnerImport,
            LearnerImport.objects.create(
                site=organisation.site,
                organisation=organisation,
                cohort=cohort,
                requested_by=user,
                status=ImportStatus.PREVIEWED,
                row_count=len(rows),
                # Only the base name, cut to the field length: the name is shown in
                # the file chip and must never carry a path.
                file_name=os.path.basename(uploaded_file.name or "")[:255],
            ),
        )
        # bulk_create bypasses save(), so the site is written here on purpose.
        LearnerImportRow.objects.bulk_create(
            [
                LearnerImportRow(
                    site=learner_import.site,
                    learner_import=learner_import,
                    line_number=int(row[LINE_KEY]),
                    email=row.get("email", ""),
                    first_name=row.get("first_name", ""),
                    last_name=row.get("last_name", ""),
                    cohort_name=row.get("cohort", ""),
                    preview_label=ImportLabel.ERROR,
                )
                for row in rows
            ]
        )
        preview_rows(learner_import, user)
    return learner_import


@dataclass(frozen=True)
class RowCheck:
    row: LearnerImportRow
    entry: LearnerEntry | None
    cohort: Cohort | None
    error: str


def _clean_email(raw: str) -> str:
    for noise in EMAIL_NOISE:
        raw = raw.replace(noise, "")
    return raw.strip()


def _length_error(email: str, row: LearnerImportRow) -> str:
    if len(email) > EMAIL_MAX_LENGTH:
        return f"The email column is longer than {EMAIL_MAX_LENGTH} characters."
    for column, value in (
        ("first_name", row.first_name),
        ("last_name", row.last_name),
        ("cohort", row.cohort_name),
    ):
        if len(value) > NAME_MAX_LENGTH:
            return f"The {column} column is longer than {NAME_MAX_LENGTH} characters."
    return ""


def check_rows(
    learner_import: LearnerImport, user: User, rows: Iterable[LearnerImportRow]
) -> Iterator[RowCheck]:
    """The shared classification steps, in order: email cleaning, lengths,
    duplicates (against every row of the import, not only `rows`) and cohort
    resolution."""
    first_line_of: dict[str, int] = {}
    for line_number, email in (
        LearnerImportRow._base_manager.filter(learner_import=learner_import)
        .order_by("line_number")
        .values_list("line_number", "email")
    ):
        first_line_of.setdefault(_clean_email(email).lower(), line_number)
    cohorts: dict[str, Cohort] | None = None
    for row in rows:
        email = _clean_email(row.email)
        error = _length_error(email, row) if email else "Email is empty."
        if not error and first_line_of[email.lower()] != row.line_number:
            error = f"Same email as line {first_line_of[email.lower()]}."
        cohort: Cohort | None = None
        cohort_name = row.cohort_name.strip()
        if not error and cohort_name:
            if cohorts is None:
                cohorts = {
                    candidate.name.lower(): candidate
                    for candidate in cohorts_visible_to(
                        user,
                        learner_import.organisation,
                        capability=ADD_COHORTMEMBERSHIP,
                    ).filter(is_active=True)
                }
            cohort = cohorts.get(cohort_name.lower())
            if cohort is None:
                error = (
                    f"No active cohort called '{cohort_name}' that you can "
                    "add learners to."
                )
        entry = (
            None
            if error
            else LearnerEntry(email, row.first_name.strip(), row.last_name.strip())
        )
        yield RowCheck(row, entry, cohort, error)


def label_for(
    check: RowCheck, result: AddLearnerResult | None
) -> tuple[ImportLabel, str]:
    """The label and reason a checked row gets once `result` is known."""
    if check.error or result is None:
        return ImportLabel.ERROR, check.error
    if result.outcome == AddOutcome.INVALID_EMAIL:
        return ImportLabel.ERROR, INVALID_EMAIL_REASON
    if result.outcome == AddOutcome.EMAIL_IN_USE_ELSEWHERE:
        return ImportLabel.ERROR, OTHER_SITE_REASON
    return LABEL_FOR[(AddOutcome(result.outcome), result.cohort_outcome)], ""


def preview_rows(learner_import: LearnerImport, user: User) -> None:
    """Label every row without writing anything but the labels. Existing
    users, learners and memberships are loaded once per distinct cohort, not
    once per row."""
    rows = list(LearnerImportRow._base_manager.filter(learner_import=learner_import))
    checks = list(check_rows(learner_import, user, rows))
    by_cohort: dict[Cohort | None, list[tuple[RowCheck, LearnerEntry]]] = defaultdict(
        list
    )
    for check in checks:
        if check.entry is not None:
            by_cohort[check.cohort].append((check, check.entry))
    results: dict[int, AddLearnerResult] = {}
    for cohort, group in by_cohort.items():
        lookup = ImportLookup.build(
            learner_import.organisation, [entry.email for _, entry in group], cohort
        )
        for check, entry in group:
            results[check.row.line_number] = classify_learner_entry(
                learner_import.organisation, entry, cohort, lookup
            )
    for check in checks:
        label, reason = label_for(check, results.get(check.row.line_number))
        check.row.preview_label, check.row.preview_reason = label, reason
    LearnerImportRow._base_manager.bulk_update(
        rows, ["preview_label", "preview_reason"]
    )


def commit_rows(learner_import: LearnerImport, user: User) -> None:
    """Add the rows that hold no final label yet, in line order, each in its
    own transaction, so a stopped commit resumes without repeating a row."""
    pending = LearnerImportRow._base_manager.filter(
        learner_import=learner_import, final_label__isnull=True
    ).order_by("line_number")
    for check in check_rows(learner_import, user, pending):
        with transaction.atomic():
            result: AddLearnerResult | None = None
            reason_override = ""
            if check.entry is not None:
                try:
                    result = add_learner(
                        learner_import.organisation, check.entry, check.cohort
                    )
                except ValueError:
                    reason_override = COHORT_UNAVAILABLE_REASON
            label, reason = label_for(check, result)
            check.row.final_label, check.row.final_reason = (
                label,
                reason_override or reason,
            )
            check.row.save(update_fields=["final_label", "final_reason"])
            LearnerImport._base_manager.filter(pk=learner_import.pk).update(
                processed_count=F("processed_count") + 1
            )


def run_learner_import(import_id: str, site_id: int) -> None:
    """Commit the import's rows and record the outcome on it.

    Callable from a background task, which has no request and so no ambient
    site: the import is read through `_base_manager` filtered on `site_id`.
    """
    learner_import = get_object_or_404(
        LearnerImport._base_manager.filter(site_id=site_id).select_related(
            "organisation", "cohort", "requested_by"
        ),
        pk=import_id,
    )
    with record_run(learner_import):
        # The gate is checked against the import's own organisation and cohort,
        # never against anything the request supplied.
        if not check_import_gate(
            learner_import.requested_by,
            learner_import.organisation,
            learner_import.cohort,
        ):
            learner_import.status = RunStatus.FAILED
            learner_import.error_message = PERMISSION_LOST_MESSAGE
            return
        commit_rows(learner_import, learner_import.requested_by)
        learner_import.status = RunStatus.DONE
