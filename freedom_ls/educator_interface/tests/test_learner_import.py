"""Learner import: labelling a file's rows for a preview and committing them."""

from __future__ import annotations

from typing import cast

import pytest

from django.contrib.sites.models import Site
from django.core.files.uploadedfile import SimpleUploadedFile

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.audit_log.models import AuditLogEntry
from freedom_ls.base.csv_import import CsvImportError
from freedom_ls.educator_interface.learner_import import (
    PERMISSION_LOST_MESSAGE,
    commit_rows,
    create_learner_import,
    run_learner_import,
)
from freedom_ls.learner_management.factories import (
    CohortFactory,
    CohortMembershipFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import (
    Cohort,
    ImportLabel,
    ImportStatus,
    Learner,
    LearnerImport,
    LearnerImportRow,
    RunStatus,
)
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.role_based_permissions.utils import assign_object_role
from freedom_ls.tests.site_context import drop_ambient_request

pytestmark = pytest.mark.django_db

HEADER = "email,first_name,last_name,cohort\n"


def _file(*lines: str, header: str = HEADER) -> SimpleUploadedFile:
    return SimpleUploadedFile(
        "learners.csv", (header + "\n".join(lines)).encode(), "text/csv"
    )


def _admin(organisation: Organisation) -> User:
    user = cast(User, UserFactory(staff=True))
    assign_object_role(user, organisation, "organisation_admin")
    return user


def _labels(learner_import: LearnerImport, field: str = "preview_label") -> list[str]:
    return [
        getattr(row, field)
        for row in LearnerImportRow.objects.filter(
            learner_import=learner_import
        ).order_by("line_number")
    ]


@pytest.fixture
def organisation(mock_site_context: Site) -> Organisation:
    return cast(Organisation, OrganisationFactory())


@pytest.fixture
def admin(organisation: Organisation) -> User:
    return _admin(organisation)


def test_a_mixed_file_is_labelled_row_by_row(
    organisation: Organisation, admin: User
) -> None:
    existing = cast(Learner, LearnerFactory(organisation=organisation))
    elsewhere_user = cast(User, UserFactory())
    CohortFactory(organisation=organisation, name="Accra")
    upload = _file(
        "new@example.com,New,Person,Accra",
        f"{existing.user.email},,,",
        f"{elsewhere_user.email},,,",
        "not-an-email,,,",
    )

    learner_import = create_learner_import(admin, organisation, None, upload)

    rows = LearnerImportRow.objects.filter(learner_import=learner_import).order_by(
        "line_number"
    )
    assert [(row.line_number, row.preview_label) for row in rows[:2]] == [
        (2, ImportLabel.NEW_ACCOUNT),
        (3, ImportLabel.ALREADY_MEMBER),
    ]
    assert rows[3].preview_label == ImportLabel.ERROR
    assert rows[3].preview_reason == "This isn't a valid email address."
    assert learner_import.status == ImportStatus.PREVIEWED
    assert learner_import.row_count == 4


def test_a_repeated_email_is_an_error_naming_the_first_line(
    organisation: Organisation, admin: User
) -> None:
    upload = _file("a@example.com,,,", "", "b@example.com,,,", "A@Example.com,,,")

    learner_import = create_learner_import(admin, organisation, None, upload)

    last = LearnerImportRow.objects.get(learner_import=learner_import, line_number=5)
    assert (last.preview_label, last.preview_reason) == (
        ImportLabel.ERROR,
        "Same email as line 2.",
    )


def test_a_blank_email_and_an_over_long_name_are_errors(
    organisation: Organisation, admin: User
) -> None:
    upload = _file(",First,Last,", f"a@example.com,{'x' * 151},,")

    learner_import = create_learner_import(admin, organisation, None, upload)

    reasons = [
        row.preview_reason
        for row in LearnerImportRow.objects.filter(
            learner_import=learner_import
        ).order_by("line_number")
    ]
    assert reasons == [
        "Email is empty.",
        "The first_name column is longer than 150 characters.",
    ]


def test_a_cohort_cell_matches_only_cohorts_the_user_can_add_to(
    organisation: Organisation,
) -> None:
    mine = cast(Cohort, CohortFactory(organisation=organisation, name="Mine"))
    CohortFactory(organisation=organisation, name="Theirs")
    inactive = CohortFactory(organisation=organisation, name="Old", is_active=False)
    cohort_admin = cast(User, UserFactory(staff=True))
    assign_object_role(cohort_admin, mine, "cohort_admin")
    upload = _file(
        "a@example.com,,,mine",
        "b@example.com,,,Theirs",
        f"c@example.com,,,{inactive.name}",
    )

    learner_import = create_learner_import(cohort_admin, organisation, None, upload)

    rows = list(
        LearnerImportRow.objects.filter(learner_import=learner_import).order_by(
            "line_number"
        )
    )
    assert rows[0].preview_label == ImportLabel.NEW_ACCOUNT
    assert rows[1].preview_reason == (
        "No active cohort called 'Theirs' that you can add learners to."
    )
    assert rows[2].preview_label == ImportLabel.ERROR


def test_a_cohort_import_ignores_the_cohort_cell_and_uses_its_own_cohort(
    organisation: Organisation, admin: User
) -> None:
    cohort = cast(Cohort, CohortFactory(organisation=organisation, name="Accra"))
    CohortFactory(organisation=organisation, name="Lagos")
    upload = _file("a@example.com,,,Lagos", "b@example.com,,,No such cohort")

    learner_import = create_learner_import(admin, organisation, cohort, upload)

    assert learner_import.cohort == cohort
    assert _labels(learner_import) == [ImportLabel.NEW_ACCOUNT] * 2


def test_a_cohort_import_adds_every_row_to_its_cohort(
    organisation: Organisation, admin: User, mock_site_context: Site
) -> None:
    cohort = cast(Cohort, CohortFactory(organisation=organisation, name="Accra"))
    existing = LearnerFactory(organisation=organisation)
    upload = _file("a@example.com,,,Lagos", f"{existing.user.email},,,")
    learner_import = create_learner_import(admin, organisation, cohort, upload)

    run_learner_import(str(learner_import.pk), mock_site_context.pk)

    assert _labels(learner_import, "final_label") == [
        ImportLabel.NEW_ACCOUNT,
        ImportLabel.ADDED_TO_COHORT,
    ]
    assert cohort.cohortmembership_set.count() == 2


def test_a_file_level_failure_stores_nothing(
    organisation: Organisation, admin: User
) -> None:
    with pytest.raises(CsvImportError):
        create_learner_import(
            admin, organisation, None, _file("a@b.c", header="name\n")
        )

    assert not LearnerImport.objects.exists()


def test_the_stored_file_name_never_carries_a_path(
    organisation: Organisation, admin: User
) -> None:
    upload = _file("a@example.com,,,")
    upload.name = "../../etc/learners.csv"

    learner_import = create_learner_import(admin, organisation, None, upload)

    assert learner_import.file_name == "learners.csv"


def test_a_preview_of_200_rows_stays_within_a_fixed_query_budget(
    organisation: Organisation, admin: User, django_assert_max_num_queries
) -> None:
    CohortFactory(organisation=organisation, name="Accra")
    upload = _file(*(f"import{n}@learners.test,A,B,Accra" for n in range(200)))

    with django_assert_max_num_queries(40):
        create_learner_import(admin, organisation, None, upload)


def test_a_commit_adds_the_good_rows_and_labels_the_bad_ones(
    organisation: Organisation, admin: User, mock_site_context: Site
) -> None:
    good = [f"import{n}@learners.test,A,B," for n in range(28)]
    upload = _file(*good, "bad,,,", ",First,,")
    learner_import = create_learner_import(admin, organisation, None, upload)

    run_learner_import(str(learner_import.pk), mock_site_context.pk)

    learner_import = LearnerImport.objects.get(pk=learner_import.pk)
    final = _labels(learner_import, "final_label")
    assert learner_import.status == RunStatus.DONE
    assert final.count(ImportLabel.NEW_ACCOUNT) == 28
    assert final.count(ImportLabel.ERROR) == 2
    assert Learner.objects.filter(organisation=organisation).count() == 28


def test_uploading_the_same_file_again_adds_nobody_and_sends_nothing(
    organisation: Organisation,
    admin: User,
    mock_site_context: Site,
    django_capture_on_commit_callbacks,
    mailoutbox,
) -> None:
    cohort = cast(Cohort, CohortFactory(organisation=organisation, name="Accra"))
    lines = [f"import{n}@learners.test,A,B,Accra" for n in range(3)]
    first = create_learner_import(admin, organisation, None, _file(*lines))
    with django_capture_on_commit_callbacks(execute=True):
        run_learner_import(str(first.pk), mock_site_context.pk)
    sent = len(mailoutbox)

    second = create_learner_import(admin, organisation, None, _file(*lines))
    with django_capture_on_commit_callbacks(execute=True):
        run_learner_import(str(second.pk), mock_site_context.pk)

    assert _labels(second) == [ImportLabel.ALREADY_MEMBER] * 3
    assert _labels(second, "final_label") == [ImportLabel.ALREADY_MEMBER] * 3
    assert len(mailoutbox) == sent
    assert cohort.cohortmembership_set.count() == 3


def test_an_existing_users_names_are_unchanged(
    organisation: Organisation, admin: User, mock_site_context: Site
) -> None:
    user = cast(User, UserFactory(first_name="Original", last_name="Name"))
    learner_import = create_learner_import(
        admin, organisation, None, _file(f"{user.email},Changed,Names,")
    )

    run_learner_import(str(learner_import.pk), mock_site_context.pk)

    user.refresh_from_db()
    assert (user.first_name, user.last_name) == ("Original", "Name")


def test_a_row_whose_state_changed_since_the_preview_reports_its_real_label(
    organisation: Organisation, admin: User, mock_site_context: Site
) -> None:
    cohort = cast(Cohort, CohortFactory(organisation=organisation, name="Accra"))
    user = cast(User, UserFactory())
    learner_import = create_learner_import(
        admin, organisation, None, _file(f"{user.email},,,Accra")
    )
    learner = cast(Learner, LearnerFactory(organisation=organisation, user=user))
    CohortMembershipFactory(learner=learner, cohort=cohort)

    run_learner_import(str(learner_import.pk), mock_site_context.pk)

    assert _labels(learner_import) == [ImportLabel.JOINED]
    assert _labels(learner_import, "final_label") == [ImportLabel.ALREADY_MEMBER]


def test_a_commit_run_again_does_not_repeat_a_row(
    organisation: Organisation,
    admin: User,
    django_capture_on_commit_callbacks,
    mailoutbox,
) -> None:
    learner_import = create_learner_import(
        admin,
        organisation,
        None,
        _file("a@example.com,,,", "b@example.com,,,", "c@example.com,,,"),
    )
    first = LearnerImportRow.objects.get(learner_import=learner_import, line_number=2)
    first.final_label = ImportLabel.NEW_ACCOUNT
    first.save(update_fields=["final_label"])

    with django_capture_on_commit_callbacks(execute=True):
        commit_rows(learner_import, admin)

    assert sorted(message.to[0] for message in mailoutbox) == [
        "b@example.com",
        "c@example.com",
    ]
    assert not User.objects.filter(email="a@example.com").exists()


def test_losing_the_gate_between_preview_and_commit_fails_the_import(
    organisation: Organisation, mock_site_context: Site
) -> None:
    requester = _admin(organisation)
    learner_import = create_learner_import(
        requester, organisation, None, _file("a@example.com,,,")
    )
    requester.object_role_assignments.all().delete()

    run_learner_import(str(learner_import.pk), mock_site_context.pk)

    learner_import = LearnerImport.objects.get(pk=learner_import.pk)
    assert learner_import.status == RunStatus.FAILED
    assert learner_import.error_message == PERMISSION_LOST_MESSAGE
    assert _labels(learner_import, "final_label") == [None]


def test_the_task_path_with_no_ambient_site_writes_site_on_every_row(
    organisation: Organisation, admin: User, mock_site_context: Site
) -> None:
    other = cast(Organisation, OrganisationFactory())
    bystander = cast(Learner, LearnerFactory(organisation=other))
    learner_import = create_learner_import(
        admin, organisation, None, _file("a@example.com,,,", "b@example.com,,,")
    )
    drop_ambient_request()

    run_learner_import(str(learner_import.pk), mock_site_context.pk)

    rows = LearnerImportRow._base_manager.filter(learner_import=learner_import)
    assert {row.site_id for row in rows} == {mock_site_context.pk}
    assert [row.final_label for row in rows] == [ImportLabel.NEW_ACCOUNT] * 2
    assert Learner._base_manager.filter(organisation=other).count() == 1
    assert Learner._base_manager.get(pk=bystander.pk).is_active


def test_a_committed_import_attributes_its_entries_to_the_importer(
    organisation: Organisation, admin: User, mock_site_context: Site
) -> None:
    """The commit called add_learner without an actor, so the entries an
    import wrote said nobody added the learners."""
    learner_import = create_learner_import(
        admin, organisation, None, _file("a@example.com,,,", "b@example.com,,,")
    )

    run_learner_import(str(learner_import.pk), mock_site_context.pk)

    entries = AuditLogEntry.unscoped.filter(action="learner.added")
    assert entries.count() == 2
    assert {entry.actor for entry in entries} == {admin}
