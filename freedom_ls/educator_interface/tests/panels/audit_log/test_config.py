"""The audit log page's access rules and its CSV export."""

from __future__ import annotations

import csv
import io
from datetime import timedelta
from typing import cast
from uuid import uuid4

import pytest

from django.test import Client
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.audit_log.factories import AuditLogEntryFactory
from freedom_ls.audit_log.models import AuditLogEntry
from freedom_ls.educator_interface.tests.helpers import (
    _audit_log_document,
    _audit_log_url,
    _get_document,
    _interface_url,
    _record_run,
)
from freedom_ls.learner_management.factories import (
    CohortFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import (
    Cohort,
)
from freedom_ls.learner_management.role_assignment import assign_role
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.tests.factories import SiteFactory
from freedom_ls.tests.site_context import site_context


def _audit_log_export(
    client: Client, organisation: Organisation, **filters: str
) -> tuple[list[str], list[list[str]], str]:
    response = client.get(
        _audit_log_url(organisation),
        {"audit_log-export": "csv", **filters},
    )
    assert response.status_code == 200
    body = b"".join(response.streaming_content).decode("utf-8-sig")
    header, *rows = list(csv.reader(io.StringIO(body, newline="")))
    return header, rows, response["Content-Disposition"]


@pytest.mark.django_db
def test_an_admin_of_another_organisation_gets_a_404_on_the_audit_log(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    other_organisation = OrganisationFactory()
    grantor = LearnerFactory(user__superuser=True).user
    admin = LearnerFactory(user__staff=True, organisation=other_organisation).user
    assign_role(grantor, admin, "organisation_admin", other_organisation)

    response = logged_in_client(admin).get(_audit_log_url(organisation))

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_cohort_admin_gets_a_404_on_the_audit_log_and_no_menu_entry(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, educator, "cohort_admin", cohort)
    client = logged_in_client(educator)

    page = _get_document(client, _interface_url(organisation.slug, "cohorts"))
    response = client.get(_audit_log_url(organisation))
    nested = client.get(_interface_url(organisation.slug, "audit-log/anything"))

    (nav,) = page.cssselect("#sidebar-nav")
    labels = [a.text_content().strip() for a in nav.cssselect("a")]
    assert ("Audit log" in labels, response.status_code, nested.status_code) == (
        False,
        404,
        404,
    )


@pytest.mark.django_db
def test_the_audit_log_toolbar_offers_the_csv_export(staff_client: Client):
    organisation = OrganisationFactory()
    AuditLogEntryFactory(target=organisation)

    document = _audit_log_document(staff_client, organisation)

    links = [
        a for a in document.cssselect("a") if a.text_content().strip() == "Export CSV"
    ]
    assert links
    assert all("audit_log-export=csv" in a.get("href") for a in links)


@pytest.mark.django_db
def test_the_audit_log_export_honours_the_who_filter(staff_client: Client):
    organisation = OrganisationFactory()
    ada = UserFactory(first_name="Ada", last_name="Admin")
    AuditLogEntryFactory(target=organisation, actor=ada, target_label="Match")
    AuditLogEntryFactory(target=organisation, actor=None, target_label="Other actor")

    _header, rows, _disposition = _audit_log_export(
        staff_client, organisation, **{"audit_log-who": str(ada.pk)}
    )

    assert [row[5] for row in rows] == ["Match"]


@pytest.mark.django_db
def test_the_audit_log_export_honours_the_what_filter(staff_client: Client):
    organisation = OrganisationFactory()
    AuditLogEntryFactory(
        target=organisation, action="cohort.created", target_label="Match"
    )
    AuditLogEntryFactory(
        target=organisation, action="role.assigned", target_label="Other action"
    )

    _header, rows, _disposition = _audit_log_export(
        staff_client, organisation, **{"audit_log-what": "cohort.created"}
    )

    assert [row[5] for row in rows] == ["Match"]


@pytest.mark.django_db
def test_the_audit_log_export_honours_the_when_filter(staff_client: Client):
    organisation = OrganisationFactory()
    AuditLogEntryFactory(target=organisation, target_label="Recent")
    AuditLogEntryFactory(
        target=organisation,
        target_label="Old",
        created_at=timezone.now() - timedelta(days=10),
    )

    _header, rows, _disposition = _audit_log_export(
        staff_client, organisation, **{"audit_log-when": "today"}
    )

    assert [row[5] for row in rows] == ["Recent"]


@pytest.mark.django_db
def test_the_audit_log_export_is_named_for_the_organisation(staff_client: Client):
    organisation = OrganisationFactory()
    AuditLogEntryFactory(target=organisation)

    _header, _rows, disposition = _audit_log_export(staff_client, organisation)

    assert disposition == (
        f'attachment; filename="audit_log-{organisation.slug}-{timezone.localdate():%Y-%m-%d}.csv"'
    )


@pytest.mark.django_db
def test_the_audit_log_export_holds_a_runs_summary_and_every_per_object_entry(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learners = [LearnerFactory(organisation=organisation) for _ in range(3)]
    run_id = uuid4()
    _record_run(organisation, learners, run_id)

    _header, rows, _disposition = _audit_log_export(staff_client, organisation)

    assert (len(rows), {row[8] for row in rows}) == (4, {str(run_id)})


@pytest.mark.django_db
def test_a_what_filter_on_the_per_object_action_drops_the_runs_summary(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learners = [LearnerFactory(organisation=organisation) for _ in range(3)]
    _record_run(organisation, learners, uuid4())

    _header, rows, _disposition = _audit_log_export(
        staff_client, organisation, **{"audit_log-what": "learner.deactivated"}
    )

    assert [row[3] for row in rows] == ["Learner deactivated"] * 3


@pytest.mark.django_db
def test_the_audit_log_export_leaves_out_another_organisations_entries(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    AuditLogEntryFactory(target=organisation, target_label="Ours")
    AuditLogEntryFactory(target=OrganisationFactory(), target_label="Theirs")

    _header, rows, _disposition = _audit_log_export(staff_client, organisation)

    assert [row[5] for row in rows] == ["Ours"]


@pytest.mark.django_db
def test_the_audit_log_export_leaves_out_another_sites_entries(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    AuditLogEntryFactory(target=organisation, target_label="Ours")
    with site_context(SiteFactory()):
        AuditLogEntryFactory(target=organisation, target_label="Other site")

    _header, rows, _disposition = _audit_log_export(staff_client, organisation)

    assert [row[5] for row in rows] == ["Ours"]


@pytest.mark.django_db
def test_the_audit_log_export_records_its_scope_and_applied_filters(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    orla = UserFactory(first_name="Orla", last_name="Admin")
    AuditLogEntryFactory(target=organisation, actor=orla, action="learner.deactivated")

    _audit_log_export(
        staff_client,
        organisation,
        **{"audit_log-who": str(orla.pk), "audit_log-what": "learner.deactivated"},
    )

    entry = AuditLogEntry.objects.get(action="audit_log.exported")
    assert entry.details == {
        "scope": "organisation",
        "scope_label": "",
        "count": 1,
        "filters": "Who: Orla Admin, What: Learner deactivated",
    }


@pytest.mark.django_db
def test_the_audit_log_export_omits_its_own_entry_and_a_second_export_holds_it(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    AuditLogEntryFactory(target=organisation, target_label="Ours")

    _header, first_rows, _disposition = _audit_log_export(staff_client, organisation)
    _header, second_rows, _disposition = _audit_log_export(staff_client, organisation)

    assert (
        [row[4] for row in first_rows if "exported" in row[4]],
        len([row for row in second_rows if "exported" in row[4]]),
    ) == ([], 1)
