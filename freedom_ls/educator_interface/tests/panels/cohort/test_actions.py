"""Deleting an empty cohort from its settings tab.

Only a cohort with no memberships and no course registrations can be deleted;
deactivated learners and inactive registrations still count.

The cohort page also renders for a cohort whose registrations granted progress.

CourseProgress protects its grant FKs, so Django's Collector raises rather than
returning a cascade preview. DeleteAction renders that preview on every GET, for
every viewer holding delete_cohort — which turned the whole panel into a 500 for
site admins and superusers, while educators (who never see the delete button)
saw nothing wrong.
"""

from __future__ import annotations

import html
import json
import uuid
from collections.abc import Callable
from typing import cast
from unittest import mock

import lxml.html
import pytest

from django.contrib.auth.models import AbstractBaseUser
from django.contrib.sites.models import Site
from django.db import connection
from django.db.models import ProtectedError
from django.http import Http404
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.audit_log.models import AuditLogEntry
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import Course, CourseAudience
from freedom_ls.educator_interface.events import (
    COHORT_CHANGED,
    LEARNER_CHANGED,
)
from freedom_ls.educator_interface.panels.cohort.actions import (
    DeleteEmptyCohortAction,
    RequiresActiveCohortMixin,
    cohort_not_empty_sentence,
)
from freedom_ls.educator_interface.panels.cohort.config import CohortConfig
from freedom_ls.educator_interface.tests.helpers import (
    REGISTERABLE_ROWS,
    _assert_message_dialog,
    _bulk_text,
    _cohort_admin_on,
    _cohort_url,
    _cohort_with_courses,
    _dialog_title,
    _empty_picker_text,
    _get_fragment,
    _membership,
    _offered_options,
    _organisation_admin_on,
    _picker_dialog,
    _post,
    _registered_cohort,
    _unregister_post_url,
    _unregister_url,
    course_per_reach_row,
)
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    CohortMembership,
    ImportStatus,
    Learner,
    LearnerImport,
)
from freedom_ls.learner_management.role_assignment import (
    assign_role,
)
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.learner_progress.utils import ensure_course_progress_record
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.panel_framework.context import PanelContext
from freedom_ls.panel_framework.events import build_hx_trigger
from freedom_ls.role_based_permissions.utils import assign_object_role
from freedom_ls.tests.audit_assertions import assert_entry


@pytest.fixture
def cohort_with_granted_progress(
    mock_site_context: Site, course_with_topic: Callable[..., Course]
) -> Cohort:
    """A cohort holding a registration that has already granted a record."""
    organisation = OrganisationFactory()
    cohort: Cohort = CohortFactory(organisation=organisation, name="Year 9 Maths")
    course = course_with_topic()
    registration = CohortCourseRegistrationFactory(cohort=cohort, course=course)
    learner = LearnerFactory(organisation=organisation)
    CohortMembershipFactory(cohort=cohort, learner=learner)
    # The receivers that would mint this defer to transaction.on_commit, which a
    # rolled-back test transaction never reaches.
    ensure_course_progress_record(learner, course, registration)
    return cohort


def _panel_url(cohort: Cohort) -> str:
    return reverse(
        "educator_interface:interface",
        kwargs={
            "organisation_slug": cohort.organisation.slug,
            "path_string": f"cohorts/{cohort.pk}",
        },
    )


def _delete_url(client: Client, cohort: Cohort) -> str:
    """The delete action's URL, on the settings tab."""
    return f"{_panel_url(cohort)}/__tabs/settings/__panels/status/__actions/delete"


@pytest.mark.django_db
def test_an_empty_cohort_is_deleted_from_its_details_panel(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> None:
    cohort = CohortFactory(organisation=OrganisationFactory(), name="Empty Cohort")
    cohort_pk = cohort.pk
    client = logged_in_client(UserFactory(superuser=True))
    url = _delete_url(client, cohort)

    response = client.delete(url)

    assert response.status_code == 204
    assert json.loads(response["HX-Location"])["path"].endswith("/cohorts")
    # No cohortChanged: the cohort page's own panels listen for it, and would
    # refetch the deleted cohort before the navigation replaced them.
    assert response["HX-Trigger"] == build_hx_trigger({}, close_modal=True)
    assert "HX-Redirect" not in response
    assert not Cohort.objects.filter(pk=cohort_pk).exists()


@pytest.mark.django_db
def test_the_cohort_pages_panels_refresh_on_cohort_changed(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> None:
    cohort = CohortFactory(organisation=OrganisationFactory(), name="Watched Cohort")
    client = logged_in_client(UserFactory(superuser=True))

    body = client.get(_panel_url(cohort)).content.decode()

    # The Overview tab holds the details, completion and attention panels.
    assert body.count('hx-trigger="cohortChanged from:body"') >= 2


@pytest.mark.django_db
def test_the_cohort_page_renders_the_delete_trigger(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> None:
    cohort = CohortFactory(organisation=OrganisationFactory(), name="Empty Cohort")
    client = logged_in_client(UserFactory(superuser=True))
    url = _delete_url(client, cohort)

    body = client.get(f"{_panel_url(cohort)}/__tabs/settings").content.decode()

    assert f'hx-get="{url}"' in body
    assert f'hx-post="{url}"' in client.get(url).content.decode()


@pytest.mark.django_db
def test_settings_tab_renders_for_a_viewer_who_can_delete_a_cohort_with_progress(
    cohort_with_granted_progress: Cohort,
    logged_in_client: Callable[[AbstractBaseUser], Client],
) -> None:
    client = logged_in_client(UserFactory(superuser=True))

    response = client.get(f"{_panel_url(cohort_with_granted_progress)}/__tabs/settings")

    assert response.status_code == 200


@pytest.mark.django_db
def test_the_settings_tab_says_why_delete_is_unavailable(
    cohort_with_granted_progress: Cohort,
    logged_in_client: Callable[[AbstractBaseUser], Client],
) -> None:
    client = logged_in_client(UserFactory(superuser=True))
    cohort = cohort_with_granted_progress
    url = _delete_url(client, cohort)

    body = client.get(f"{_panel_url(cohort)}/__tabs/settings").content.decode()

    assert cohort_not_empty_sentence(cohort) in html.unescape(body)
    assert f'hx-get="{url}"' not in body


def _import_into(cohort: Cohort, status: str) -> LearnerImport:
    learner_import: LearnerImport = LearnerImport.objects.create(
        organisation=cohort.organisation,
        cohort=cohort,
        requested_by=UserFactory(superuser=True),
        status=status,
        file_name="learners.csv",
    )
    return learner_import


@pytest.mark.django_db
@pytest.mark.parametrize(
    "status", [ImportStatus.PREVIEWED, ImportStatus.QUEUED, ImportStatus.RUNNING]
)
def test_an_unfinished_import_into_the_cohort_blocks_the_delete(
    mock_site_context: Site,
    logged_in_client: Callable[[AbstractBaseUser], Client],
    status: str,
) -> None:
    """LearnerImport.cohort is SET_NULL, so deleting the cohort under a
    previewed import silently turned it into an import into the organisation."""
    cohort = CohortFactory(organisation=OrganisationFactory(), name="Importing")
    _import_into(cohort, status)
    client = logged_in_client(UserFactory(superuser=True))
    url = _delete_url(client, cohort)
    sentence = (
        "Importing can't be deleted while a learner import into it is in progress."
    )

    settings_tab = client.get(f"{_panel_url(cohort)}/__tabs/settings").content.decode()
    response = client.delete(url)

    assert sentence in html.unescape(settings_tab)
    assert f'hx-get="{url}"' not in settings_tab
    assert response.status_code == 422
    assert sentence in html.unescape(response.content.decode())
    assert Cohort.objects.filter(pk=cohort.pk).exists()


@pytest.mark.django_db
def test_a_finished_import_into_the_cohort_does_not_block_the_delete(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> None:
    cohort = CohortFactory(organisation=OrganisationFactory(), name="Imported")
    _import_into(cohort, ImportStatus.DONE)
    client = logged_in_client(UserFactory(superuser=True))

    response = client.delete(_delete_url(client, cohort))

    assert response.status_code == 204
    assert not Cohort.objects.filter(pk=cohort.pk).exists()


@pytest.mark.django_db
def test_the_delete_dialog_has_a_heading_naming_the_cohort_and_cancel_then_delete(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> None:
    cohort = CohortFactory(organisation=OrganisationFactory(), name="Empty Cohort")
    client = logged_in_client(UserFactory(superuser=True))
    url = _delete_url(client, cohort)

    document = lxml.html.fromstring(client.get(url).content)

    (heading,) = document.cssselect("#app-modal-title")
    assert heading.text_content().strip() == "Delete Empty Cohort?"
    names = [
        el.text_content().split()[0]
        for el in document.iter("button")
        if el.text_content().strip()
    ]
    assert names[-2:] == ["Cancel", "Delete"]


@pytest.mark.django_db
def test_submitting_the_blocked_delete_answers_instead_of_erroring(
    cohort_with_granted_progress: Cohort,
    logged_in_client: Callable[[AbstractBaseUser], Client],
) -> None:
    client = logged_in_client(UserFactory(superuser=True))
    url = _delete_url(client, cohort_with_granted_progress)

    response = client.delete(url)

    assert response.status_code == 422
    assert cohort_not_empty_sentence(cohort_with_granted_progress) in html.unescape(
        response.content.decode()
    )
    assert CourseProgress.objects.filter(
        cohort_registration__cohort=cohort_with_granted_progress
    ).exists()


@pytest.mark.django_db
def test_a_cohort_viewers_pasted_delete_url_answers_404_and_keeps_the_cohort(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> None:
    """A cohort viewer can open the cohort but not its settings tab, so the
    delete action beneath that tab is not reachable either."""
    cohort = CohortFactory(organisation=OrganisationFactory())
    url = _delete_url(logged_in_client(UserFactory(superuser=True)), cohort)
    educator = UserFactory(staff=True)
    assign_object_role(educator, cohort, "cohort_viewer")
    client = logged_in_client(educator)
    assert client.get(_panel_url(cohort)).status_code == 200

    response = client.get(url)

    assert response.status_code == 404
    assert Cohort.objects.filter(pk=cohort.pk).exists()


@pytest.mark.django_db
def test_the_delete_dialog_body_says_the_delete_cannot_be_undone(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> None:
    cohort = CohortFactory(organisation=OrganisationFactory(), name="Empty Cohort")
    client = logged_in_client(UserFactory(superuser=True))
    url = _delete_url(client, cohort)

    document = lxml.html.fromstring(client.get(url).content)

    body = document.cssselect("form > div")[0]
    assert "cannot be undone" in body.text_content()
    assert "cohort" in body.text_content()


@pytest.fixture(params=["deactivated learner", "inactive registration"])
def cohort_holding_only_dormant_rows(
    request: pytest.FixtureRequest, mock_site_context: Site
) -> Cohort:
    cohort: Cohort = CohortFactory(organisation=OrganisationFactory(), name="Dormant")
    if request.param == "deactivated learner":
        CohortMembershipFactory(
            cohort=cohort,
            learner=LearnerFactory(organisation=cohort.organisation, is_active=False),
        )
    else:
        CohortCourseRegistrationFactory(cohort=cohort, is_active=False)
    return cohort


@pytest.mark.django_db
def test_a_cohort_holding_only_dormant_rows_offers_no_delete_and_says_why(
    cohort_holding_only_dormant_rows: Cohort,
    logged_in_client: Callable[[AbstractBaseUser], Client],
) -> None:
    cohort = cohort_holding_only_dormant_rows
    client = logged_in_client(UserFactory(superuser=True))
    url = _delete_url(client, cohort)

    body = client.get(f"{_panel_url(cohort)}/__tabs/settings").content.decode()

    assert f'hx-get="{url}"' not in body
    assert cohort_not_empty_sentence(cohort) in html.unescape(body)


@pytest.mark.django_db
def test_deleting_a_cohort_holding_only_dormant_rows_answers_422_and_keeps_it(
    cohort_holding_only_dormant_rows: Cohort,
    logged_in_client: Callable[[AbstractBaseUser], Client],
) -> None:
    cohort = cohort_holding_only_dormant_rows
    client = logged_in_client(UserFactory(superuser=True))

    response = client.delete(_delete_url(client, cohort))

    assert response.status_code == 422
    assert cohort_not_empty_sentence(cohort) in html.unescape(response.content.decode())
    assert Cohort.objects.filter(pk=cohort.pk).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("method", ["get", "delete"])
def test_a_non_empty_cohort_is_refused_without_collecting_what_a_delete_would_remove(
    cohort_holding_only_dormant_rows: Cohort,
    logged_in_client: Callable[[AbstractBaseUser], Client],
    method: str,
) -> None:
    """The collector walks every membership and registration of the cohort,
    which a refusal with a known reason has no use for."""
    cohort = cohort_holding_only_dormant_rows
    client = logged_in_client(UserFactory(superuser=True))

    with mock.patch.object(
        DeleteEmptyCohortAction, "get_cascade_summary"
    ) as get_cascade_summary:
        response = getattr(client, method)(_delete_url(client, cohort))

    assert cohort_not_empty_sentence(cohort) in html.unescape(response.content.decode())
    get_cascade_summary.assert_not_called()


@pytest.mark.django_db
def test_a_delete_of_a_cohort_that_gained_a_member_answers_422_and_keeps_it(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> None:
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation, name="Stale page")
    client = logged_in_client(UserFactory(superuser=True))
    url = _delete_url(client, cohort)
    assert client.get(url).status_code == 200
    membership = CohortMembershipFactory(
        cohort=cohort, learner=LearnerFactory(organisation=organisation)
    )

    response = client.delete(url)

    assert response.status_code == 422
    assert cohort_not_empty_sentence(cohort) in html.unescape(response.content.decode())
    assert Cohort.objects.filter(pk=cohort.pk).exists()
    assert CohortMembership.objects.filter(pk=membership.pk).exists()


@pytest.mark.django_db
def test_a_delete_of_a_cohort_already_deleted_answers_the_unavailable_fragment(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> None:
    """Two admins confirm Delete together: the second finds no row and gets
    the modal's "no longer available" copy, not a server error."""
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation, name="Going twice")
    client = logged_in_client(UserFactory(superuser=True))
    url = _delete_url(client, cohort)
    assert client.get(url).status_code == 200
    action = DeleteEmptyCohortAction()
    ctx = PanelContext(
        request=client.get(url, HTTP_HX_REQUEST="true").wsgi_request,
        instance=cohort,
        base_url=f"{_panel_url(cohort)}/__tabs/settings",
        name="settings",
        config=CohortConfig,
    )
    Cohort.objects.filter(pk=cohort.pk).delete()

    with pytest.raises(Http404):
        action.handle_submit(ctx)


@pytest.mark.django_db
def test_deleting_a_cohort_writes_an_entry_that_keeps_its_name(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> None:
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation, name="Gone soon")
    cohort_pk = cohort.pk
    actor = UserFactory(superuser=True)
    client = logged_in_client(actor)

    client.delete(_delete_url(client, cohort))

    entry = AuditLogEntry.unscoped.get()
    assert (entry.action, entry.actor, entry.organisation) == (
        "cohort.deleted",
        actor,
        organisation,
    )
    assert entry.target_label == "Gone soon"
    assert entry.target_object_id == str(cohort_pk)
    assert not Cohort.objects.filter(pk=cohort_pk).exists()


@pytest.mark.django_db
def test_a_deleted_cohort_shows_by_name_in_the_organisation_audit_log(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> None:
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation, name="Vanished group")
    client = logged_in_client(UserFactory(superuser=True))
    client.delete(_delete_url(client, cohort))

    response = client.get(
        reverse(
            "educator_interface:interface",
            kwargs={
                "organisation_slug": organisation.slug,
                "path_string": "audit-log",
            },
        )
    )

    assert "Vanished group" in html.unescape(response.content.decode())


@pytest.mark.django_db
def test_a_blocked_delete_writes_no_entry(
    cohort_with_granted_progress: Cohort,
    logged_in_client: Callable[[AbstractBaseUser], Client],
) -> None:
    client = logged_in_client(UserFactory(superuser=True))

    client.delete(_delete_url(client, cohort_with_granted_progress))

    assert not AuditLogEntry.unscoped.exists()


@pytest.mark.django_db
def test_a_protected_error_on_delete_answers_422_and_leaves_no_entry(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> None:
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    client = logged_in_client(UserFactory(superuser=True))
    url = _delete_url(client, cohort)
    blocker = LearnerFactory(organisation=organisation)

    with mock.patch.object(
        Cohort, "delete", side_effect=ProtectedError("protected", {blocker})
    ):
        response = client.delete(url)

    assert response.status_code == 422
    assert Cohort.objects.filter(pk=cohort.pk).exists()
    assert not AuditLogEntry.unscoped.exists()


@pytest.mark.django_db
def test_an_admin_of_another_organisation_gets_a_404_on_the_delete(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> None:
    cohort = CohortFactory(organisation=OrganisationFactory())
    outsider = UserFactory(staff=True)
    assign_object_role(outsider, OrganisationFactory(), "organisation_admin")
    client = logged_in_client(outsider)

    response = client.delete(_delete_url(client, cohort))

    assert response.status_code == 404
    assert Cohort.objects.filter(pk=cohort.pk).exists()
    assert not AuditLogEntry.unscoped.filter(action="cohort.deleted").exists()


@pytest.mark.django_db
def test_the_delete_dialog_renders_the_optional_reason_field(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> None:
    cohort = CohortFactory(organisation=OrganisationFactory())
    client = logged_in_client(UserFactory(superuser=True))

    document = lxml.html.fromstring(client.get(_delete_url(client, cohort)).content)

    (field,) = document.cssselect("form input[name='reason']")
    assert field.get("maxlength") == "500"
    assert "Reason (optional)" in document.text_content()


@pytest.mark.django_db
def test_a_reason_posted_with_the_delete_reaches_the_entry(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> None:
    cohort = CohortFactory(organisation=OrganisationFactory())
    client = logged_in_client(UserFactory(superuser=True))

    response = client.post(
        _delete_url(client, cohort), {"reason": " Merged into another cohort "}
    )

    assert response.status_code == 204
    assert not Cohort.objects.filter(pk=cohort.pk).exists()
    assert AuditLogEntry.unscoped.get().reason == "Merged into another cohort"


@pytest.mark.django_db
def test_deleting_a_cohort_records_the_roles_removed_with_it(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> None:
    """The roles are gone with the cohort; the log says whose, by whom and why."""
    cohort = CohortFactory(organisation=OrganisationFactory(), name="Cohort A")
    admin = UserFactory()
    assign_object_role(admin, cohort, "cohort_admin")
    deleter = UserFactory(superuser=True)
    client = logged_in_client(deleter)

    client.post(_delete_url(client, cohort), {"reason": "Merged"})

    entries = list(AuditLogEntry.unscoped.order_by("created_at"))
    assert [entry.action for entry in entries] == [
        "role.assigned",
        "role.removed",
        "cohort.deleted",
    ]
    removed = entries[1]
    assert (removed.actor, removed.reason, removed.target_label) == (
        deleter,
        "Merged",
        admin.display_name,
    )


@pytest.mark.django_db
def test_a_delete_posted_with_no_reason_is_allowed(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> None:
    cohort = CohortFactory(organisation=OrganisationFactory())
    client = logged_in_client(UserFactory(superuser=True))

    response = client.post(_delete_url(client, cohort))

    assert response.status_code == 204
    assert AuditLogEntry.unscoped.get().reason == ""


@pytest.mark.django_db
def test_a_delete_reason_over_500_characters_answers_422_and_keeps_the_cohort(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> None:
    cohort = CohortFactory(organisation=OrganisationFactory())
    client = logged_in_client(UserFactory(superuser=True))

    response = client.post(_delete_url(client, cohort), {"reason": "x" * 501})

    assert response.status_code == 422
    assert "at most 500 characters" in response.content.decode()
    assert Cohort.objects.filter(pk=cohort.pk).exists()
    assert not AuditLogEntry.unscoped.exists()


@pytest.mark.django_db
def test_a_posted_delete_of_a_non_empty_cohort_is_refused_as_before(
    cohort_with_granted_progress: Cohort,
    logged_in_client: Callable[[AbstractBaseUser], Client],
) -> None:
    client = logged_in_client(UserFactory(superuser=True))

    response = client.post(
        _delete_url(client, cohort_with_granted_progress), {"reason": "Tidy up"}
    )

    assert response.status_code == 422
    assert cohort_not_empty_sentence(cohort_with_granted_progress) in html.unescape(
        response.content.decode()
    )
    assert Cohort.objects.filter(pk=cohort_with_granted_progress.pk).exists()
    assert not AuditLogEntry.unscoped.exists()


@pytest.mark.django_db
def test_renaming_a_cohort_onto_a_sibling_name_answers_422_and_keeps_the_name(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    CohortFactory(organisation=organisation, name="Year 10 Science")
    cohort = CohortFactory(organisation=organisation, name="Year 11 Science")

    response = _post(
        staff_client,
        _cohort_url(organisation, cohort, "/__actions/edit"),
        {"name": "Year 10 Science"},
    )

    cohort.refresh_from_db()
    assert response.status_code == 422
    assert "Another cohort already has this name." in response.content.decode()
    assert cohort.name == "Year 11 Science"
    # The 422 is the inline form itself, holding what was typed, not a dialog.
    document = lxml.html.fromstring(f"<div>{response.content.decode()}</div>")
    (form,) = document.cssselect("form#cohort-name-form")
    assert form.cssselect("input[name=name]")[0].get("value") == "Year 10 Science"
    assert not document.cssselect("header")


@pytest.mark.django_db
def test_the_rename_fragment_is_the_inline_form_holding_the_current_name(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation, name="Year 11 Science")

    response = staff_client.get(
        _cohort_url(organisation, cohort, "/__actions/edit"), HTTP_HX_REQUEST="true"
    )

    assert response.status_code == 200
    document = lxml.html.fromstring(f"<div>{response.content.decode()}</div>")
    (form,) = document.cssselect("form#cohort-name-form")
    (name,) = form.cssselect("input[name=name]")
    assert name.get("value") == "Year 11 Science"
    assert name.get("autofocus") is None


@pytest.mark.django_db
def test_an_empty_cohort_name_shows_the_bare_message_as_an_announced_field_error(
    staff_client: Client,
) -> None:
    """A field error in the inline form used to repeat the field's label, carry
    no role and leave the input unlinked from it."""
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation, name="Year 11 Science")

    response = _post(
        staff_client,
        _cohort_url(organisation, cohort, "/__actions/edit"),
        {"name": ""},
    )

    document = lxml.html.fromstring(f"<div>{response.content.decode()}</div>")
    (name,) = document.cssselect("form#cohort-name-form input[name=name]")
    (error,) = document.cssselect("form#cohort-name-form [role=alert]")
    assert response.status_code == 422
    assert error.text_content().strip() == "This field is required."
    assert error.get("id")
    assert name.get("aria-describedby") == error.get("id")
    assert name.get("aria-invalid") == "true"
    assert not document.cssselect("[data-error-summary]")


@pytest.mark.django_db
def test_an_inline_form_field_without_an_error_is_neither_invalid_nor_described(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation, name="Year 11 Science")

    response = staff_client.get(
        _cohort_url(organisation, cohort, "/__actions/edit"), HTTP_HX_REQUEST="true"
    )

    document = lxml.html.fromstring(f"<div>{response.content.decode()}</div>")
    (name,) = document.cssselect("form#cohort-name-form input[name=name]")
    assert name.get("aria-invalid") is None
    assert name.get("aria-describedby") is None
    assert not document.cssselect("[role=alert]")


@pytest.mark.django_db
def test_a_rename_answers_204_with_the_new_title_for_the_page(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation, name="Year 11 Science")

    response = _post(
        staff_client,
        _cohort_url(organisation, cohort, "/__actions/edit"),
        {"name": "Year 12 Science"},
    )

    assert response.status_code == 204
    trigger = json.loads(response["HX-Trigger"])
    assert COHORT_CHANGED in trigger
    assert trigger["instanceTitleChanged"]["title"] == "Year 12 Science"


@pytest.mark.django_db
def test_deactivate_fragment_names_how_many_courses_stop_giving_access(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 2, name="Evening group")

    text = _get_fragment(
        staff_client, _cohort_url(organisation, cohort, "/__actions/deactivate")
    )

    assert "Deactivate Evening group" in text
    assert "stop giving access to its 2 courses" in text


@pytest.mark.django_db
def test_deactivate_fragment_says_why_a_non_empty_cohort_cannot_be_deleted(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 1, name="Evening group")
    CohortMembershipFactory(
        cohort=cohort, learner=LearnerFactory(organisation=organisation)
    )

    text = _get_fragment(
        staff_client, _cohort_url(organisation, cohort, "/__actions/deactivate")
    )

    assert (
        "Evening group can't be deleted while it has 1 learner and 1 course "
        "registration, counting inactive learners and inactive registrations." in text
    )


@pytest.mark.django_db
def test_deactivate_fragment_of_an_empty_cohort_does_not_mention_deleting(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 0)

    text = _get_fragment(
        staff_client, _cohort_url(organisation, cohort, "/__actions/deactivate")
    )

    assert "can't be deleted" not in text


@pytest.mark.django_db
def test_deactivate_post_sets_the_cohort_inactive(staff_client: Client) -> None:
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 1)

    _post(staff_client, _cohort_url(organisation, cohort, "/__actions/deactivate"))

    cohort.refresh_from_db()
    assert cohort.is_active is False


@pytest.mark.django_db
def test_deactivate_post_answers_204_with_a_location_to_the_cohort_page(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 1)

    response = _post(
        staff_client, _cohort_url(organisation, cohort, "/__actions/deactivate")
    )

    assert response.status_code == 204
    assert json.loads(response["HX-Location"])["path"] == _cohort_url(
        organisation, cohort
    )


@pytest.mark.django_db
def test_stale_deactivate_on_an_inactive_cohort_answers_422_and_changes_nothing(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 1, is_active=False)

    response = _post(
        staff_client, _cohort_url(organisation, cohort, "/__actions/deactivate")
    )

    cohort.refresh_from_db()
    assert response.status_code == 422
    assert "Someone else may have deactivated it already." in " ".join(
        response.content.decode().split()
    )
    assert cohort.is_active is False
    assert not AuditLogEntry.unscoped.filter(action="cohort.deactivated").exists()


def _locks_the_cohort_row(captured: CaptureQueriesContext) -> bool:
    return any(
        'freedom_ls_learner_management_cohort"' in query["sql"]
        and "FOR UPDATE" in query["sql"]
        for query in captured.captured_queries
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("is_active", "action_name"), [(True, "deactivate"), (False, "reactivate")]
)
def test_a_cohort_state_change_locks_the_cohort_row_before_writing_its_entry(
    staff_client: Client, is_active: bool, action_name: str
) -> None:
    """Two overlapping submits must not each see the old state and each write
    an entry for the one change, so the state is re-read under a row lock."""
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 1, is_active=is_active)

    with CaptureQueriesContext(connection) as captured:
        response = _post(
            staff_client, _cohort_url(organisation, cohort, f"/__actions/{action_name}")
        )

    assert response.status_code == 204
    assert _locks_the_cohort_row(captured)


@pytest.mark.django_db
def test_reactivate_fragment_names_how_many_courses_give_access_again(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 3, name="Old group", is_active=False)

    text = _get_fragment(
        staff_client, _cohort_url(organisation, cohort, "/__actions/reactivate")
    )

    assert "Reactivate Old group" in text
    assert "give access to its 3 courses again" in text


@pytest.mark.django_db
def test_reactivate_post_sets_the_cohort_active(staff_client: Client) -> None:
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 1, is_active=False)

    response = _post(
        staff_client, _cohort_url(organisation, cohort, "/__actions/reactivate")
    )

    cohort.refresh_from_db()
    assert response.status_code == 204
    assert cohort.is_active is True


@pytest.mark.django_db
def test_reactivate_post_from_a_tab_navigates_back_to_that_tab(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 1, is_active=False)
    tab_path = _cohort_url(organisation, cohort, "/courses")

    response = staff_client.post(
        _cohort_url(organisation, cohort, "/__actions/reactivate"),
        HTTP_HX_REQUEST="true",
        HTTP_HX_CURRENT_URL=f"http://testserver{tab_path}",
    )

    assert json.loads(response["HX-Location"])["path"] == tab_path


@pytest.mark.django_db
def test_stale_reactivate_on_an_active_cohort_answers_422(staff_client: Client) -> None:
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 1)

    response = _post(
        staff_client, _cohort_url(organisation, cohort, "/__actions/reactivate")
    )

    assert response.status_code == 422
    assert "is already active" in response.content.decode()
    assert not AuditLogEntry.unscoped.filter(action="cohort.reactivated").exists()


@pytest.mark.django_db
def test_a_reason_posted_to_a_dialog_without_a_reason_field_is_ignored(
    staff_client: Client,
) -> None:
    """Reactivate takes no reason, so a hand-made POST carrying one, however
    long, neither fails nor reaches the entry."""
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 1, is_active=False)

    response = _post(
        staff_client,
        _cohort_url(organisation, cohort, "/__actions/reactivate"),
        {"reason": "x" * 600},
    )

    assert response.status_code == 204
    assert AuditLogEntry.unscoped.get(action="cohort.reactivated").reason == ""


@pytest.mark.django_db
def test_cohort_not_empty_sentence_counts_inactive_learners_and_inactive_registrations(
    mock_site_context: Site,
) -> None:
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 0, name="Evening group")
    inactive_learner = LearnerFactory(organisation=organisation, is_active=False)
    CohortMembershipFactory(cohort=cohort, learner=inactive_learner)
    CohortMembershipFactory(
        cohort=cohort, learner=LearnerFactory(organisation=organisation)
    )
    CohortCourseRegistrationFactory(cohort=cohort, is_active=False)

    sentence = cohort_not_empty_sentence(cohort)

    assert sentence == (
        "Evening group can't be deleted while it has 2 learners and 1 course "
        "registration, counting inactive learners and inactive registrations."
    )


@pytest.mark.django_db
def test_not_empty_sentence_pluralises_course_registrations(
    mock_site_context: Site,
) -> None:
    cohort = _cohort_with_courses(OrganisationFactory(), 2, name="Evening group")

    sentence = cohort_not_empty_sentence(cohort)

    assert "while it has 2 course registrations, counting" in sentence


@pytest.mark.django_db
def test_not_empty_sentence_never_names_a_zero_count(mock_site_context: Site) -> None:
    """ "0 learners" reads as a reason, and is not one."""
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 0, name="Evening group")
    CohortMembershipFactory(
        cohort=cohort, learner=LearnerFactory(organisation=organisation)
    )

    sentence = cohort_not_empty_sentence(cohort)

    assert "while it has 1 learner, counting" in sentence
    assert "0 course" not in sentence


@pytest.mark.django_db
def test_not_empty_sentence_is_empty_for_an_empty_cohort(
    mock_site_context: Site,
) -> None:
    cohort = _cohort_with_courses(OrganisationFactory(), 0)

    assert cohort_not_empty_sentence(cohort) == ""


@pytest.mark.django_db
def test_an_inactive_cohorts_settings_tab_renders_no_rename_form(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 0, is_active=False)

    response = staff_client.get(_cohort_url(organisation, cohort, "/__tabs/settings"))

    document = lxml.html.fromstring(response.content.decode())
    assert not document.cssselect("form#cohort-name-form")


@pytest.mark.django_db
def test_editing_an_inactive_cohort_answers_422_with_the_inactive_fragment(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 0, name="Old group", is_active=False)

    response = _post(
        staff_client,
        _cohort_url(organisation, cohort, "/__actions/edit"),
        {"name": "New name"},
    )

    assert response.status_code == 422
    assert "to change its name." in " ".join(response.content.decode().split())
    assert "Old group is inactive" in response.content.decode()
    # The form targets itself, so the notice is sent to the dialog instead.
    assert response["HX-Retarget"] == "#app-modal-body"
    assert response["HX-Reswap"] == "innerHTML"


def _all_subclasses(cls: type) -> set[type]:
    found: set[type] = set()
    for subclass in cls.__subclasses__():
        found |= {subclass} | _all_subclasses(subclass)
    return found


def test_every_action_guarded_by_an_active_cohort_names_what_it_blocks() -> None:
    guarded = _all_subclasses(RequiresActiveCohortMixin)

    assert guarded
    assert all(
        isinstance(getattr(subclass, "blocked_phrase", None), str)
        for subclass in guarded
        if subclass.refuse_inactive is RequiresActiveCohortMixin.refuse_inactive
    )


@pytest.mark.django_db
def test_editing_an_inactive_cohort_leaves_its_name_unchanged(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 0, name="Old group", is_active=False)

    _post(
        staff_client,
        _cohort_url(organisation, cohort, "/__actions/edit"),
        {"name": "New name"},
    )

    cohort.refresh_from_db()
    assert cohort.name == "Old group"


def _register_url(organisation: Organisation, cohort: Cohort) -> str:
    return _cohort_url(organisation, cohort, "/__tabs/courses/__actions/register")


@pytest.mark.django_db
def test_register_fragment_title_names_the_cohort(staff_client: Client) -> None:
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 0, name="Evening group")

    text = _get_fragment(staff_client, _register_url(organisation, cohort))

    assert "Register Evening group for a course?" in text


@pytest.mark.django_db
def test_the_cohort_register_dialog_names_the_chosen_course(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 0, name="Evening group")
    course = CourseFactory(title="Algebra")

    document = _picker_dialog(
        staff_client, _register_url(organisation, cohort) + f"?course={course.pk}"
    )

    assert _dialog_title(document) == "Register Evening group for Algebra?"


@pytest.mark.django_db
def test_register_post_answers_204_with_a_location_to_the_courses_tab(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> None:
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 0)
    course = CourseFactory()
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, educator, "cohort_admin", cohort)

    response = _post(
        logged_in_client(educator),
        _register_url(organisation, cohort),
        {"course": str(course.pk)},
    )

    assert response.status_code == 204
    assert json.loads(response["HX-Location"])["path"] == _cohort_url(
        organisation, cohort, "/__tabs/courses"
    )


@pytest.mark.django_db
def test_register_post_creates_the_registration(staff_client: Client) -> None:
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 0)
    course = CourseFactory()

    _post(
        staff_client,
        _register_url(organisation, cohort),
        {"course": str(course.pk)},
    )

    assert cohort.course_registrations.filter(course=course, is_active=True).exists()


@pytest.mark.django_db
def test_register_post_for_a_course_closed_to_the_organisation_answers_422(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 0)
    course = CourseFactory(audience=CourseAudience.ORGANISATION_LEARNERS)
    course.organisations.add(OrganisationFactory())

    response = _post(
        staff_client,
        _register_url(organisation, cohort),
        {"course": str(course.pk)},
    )

    assert response.status_code == 422
    assert not cohort.course_registrations.exists()


@pytest.mark.django_db
def test_register_post_on_an_inactive_cohort_answers_422_and_creates_no_row(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 0, name="Old group", is_active=False)
    course = CourseFactory()

    response = _post(
        staff_client,
        _register_url(organisation, cohort),
        {"course": str(course.pk)},
    )

    assert response.status_code == 422
    assert "to register it for a course." in " ".join(response.content.decode().split())
    assert "Old group is inactive" in response.content.decode()
    assert not cohort.course_registrations.exists()


def _member(
    organisation: Organisation, cohort: Cohort, first_name: str = "Ada"
) -> Learner:
    learner = cast(
        Learner,
        LearnerFactory(
            organisation=organisation,
            user__first_name=first_name,
            user__last_name="Lee",
        ),
    )
    CohortMembershipFactory(cohort=cohort, learner=learner)
    return learner


@pytest.mark.django_db
def test_unregister_fragment_title_names_the_cohort_and_course(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    cohort, registration = _registered_cohort(organisation, name="Evening group")

    text = _get_fragment(
        staff_client, _unregister_url(organisation, cohort, registration)
    )

    assert "Deactivate Evening group's registration for Algebra" in text


@pytest.mark.django_db
def test_unregister_fragment_counts_members_who_lose_access(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    cohort, registration = _registered_cohort(organisation)
    _member(organisation, cohort, "Ada")
    _member(organisation, cohort, "Bea")
    kept = _member(organisation, cohort, "Cy")
    LearnerCourseRegistrationFactory(
        learner=kept, course=registration.course, is_active=True
    )

    text = _get_fragment(
        staff_client, _unregister_url(organisation, cohort, registration)
    )

    assert "2 learners lose access to Algebra." in text


@pytest.mark.django_db
def test_unregister_fragment_names_a_member_kept_by_an_individual_registration(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    cohort, registration = _registered_cohort(organisation)
    kept = _member(organisation, cohort, "Cy")
    LearnerCourseRegistrationFactory(
        learner=kept, course=registration.course, is_active=True
    )

    text = _get_fragment(
        staff_client, _unregister_url(organisation, cohort, registration)
    )

    assert "These learners keep access through another registration: Cy Lee." in text


@pytest.mark.django_db
def test_unregister_fragment_names_a_member_kept_by_another_cohort(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    cohort, registration = _registered_cohort(organisation)
    kept = _member(organisation, cohort, "Dee")
    other = CohortFactory(organisation=organisation)
    CohortMembershipFactory(cohort=other, learner=kept)
    CohortCourseRegistrationFactory(cohort=other, course=registration.course)

    text = _get_fragment(
        staff_client, _unregister_url(organisation, cohort, registration)
    )

    assert "keep access through another registration: Dee Lee." in text


@pytest.mark.django_db
def test_unregister_fragment_names_the_first_ten_keepers_and_counts_the_rest(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    cohort, registration = _registered_cohort(organisation)
    for index in range(12):
        learner = _member(organisation, cohort, f"Keeper{index:02d}")
        LearnerCourseRegistrationFactory(
            learner=learner, course=registration.course, is_active=True
        )

    text = _get_fragment(
        staff_client, _unregister_url(organisation, cohort, registration)
    )

    assert "Keeper09 Lee and 2 more." in text
    assert "Keeper10" not in text


@pytest.mark.django_db
def test_unregister_fragment_omits_the_keepers_sentence_when_nobody_keeps_access(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    cohort, registration = _registered_cohort(organisation)
    _member(organisation, cohort)

    text = _get_fragment(
        staff_client, _unregister_url(organisation, cohort, registration)
    )

    assert "keep access through another registration" not in text


@pytest.mark.django_db
def test_unregister_post_deactivates_the_registration(staff_client: Client) -> None:
    organisation = OrganisationFactory()
    cohort, registration = _registered_cohort(organisation)

    _post(
        staff_client,
        _unregister_post_url(organisation, cohort),
        {"registration": str(registration.pk)},
    )

    registration.refresh_from_db()
    assert registration.is_active is False


@pytest.mark.django_db
def test_unregister_post_answers_204_with_a_location_to_the_courses_tab(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    cohort, registration = _registered_cohort(organisation)

    response = _post(
        staff_client,
        _unregister_post_url(organisation, cohort),
        {"registration": str(registration.pk)},
    )

    assert response.status_code == 204
    assert json.loads(response["HX-Location"])["path"] == _cohort_url(
        organisation, cohort, "/__tabs/courses"
    )


@pytest.mark.django_db
def test_a_cohort_admin_can_unregister_on_their_own_cohort(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> None:
    organisation = OrganisationFactory()
    cohort, registration = _registered_cohort(organisation)
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, educator, "cohort_admin", cohort)

    response = _post(
        logged_in_client(educator),
        _unregister_post_url(organisation, cohort),
        {"registration": str(registration.pk)},
    )

    assert response.status_code == 204


@pytest.mark.django_db
def test_unregister_with_a_registration_from_another_cohort_answers_404(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    cohort, _ = _registered_cohort(organisation)
    _, foreign = _registered_cohort(organisation, "Geometry")

    response = staff_client.get(
        _unregister_url(organisation, cohort, foreign), HTTP_HX_REQUEST="true"
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_unregister_with_a_registration_from_another_cohort_changes_nothing(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    cohort, _ = _registered_cohort(organisation)
    _, foreign = _registered_cohort(organisation, "Geometry")

    _post(
        staff_client,
        _unregister_post_url(organisation, cohort),
        {"registration": str(foreign.pk)},
    )

    foreign.refresh_from_db()
    assert foreign.is_active is True


@pytest.mark.django_db
def test_unregister_with_an_inactive_registration_answers_404(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    registration = CohortCourseRegistrationFactory(cohort=cohort, is_active=False)

    response = staff_client.get(
        _unregister_url(organisation, cohort, registration), HTTP_HX_REQUEST="true"
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_unregister_with_a_malformed_registration_answers_404(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    cohort, _ = _registered_cohort(organisation)

    response = staff_client.get(
        _unregister_url(organisation, cohort, "not-a-uuid"), HTTP_HX_REQUEST="true"
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_the_courses_tab_footer_offers_register_but_no_unregister_button(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    cohort, _ = _registered_cohort(organisation)

    response = staff_client.get(
        _cohort_url(organisation, cohort, "/__tabs/courses"), HTTP_HX_REQUEST="true"
    )

    footer_urls = [
        button.get("hx-get")
        for button in lxml.html.fromstring(response.content.decode()).cssselect(
            "button[hx-get]"
        )
    ]
    register_url = _register_url(organisation, cohort)
    assert register_url in footer_urls
    assert not [
        url
        for url in footer_urls
        if url.endswith("/__actions/deactivate_cohort_registration")
    ]


@pytest.mark.django_db
def test_unregister_post_on_an_inactive_cohort_answers_422_and_changes_nothing(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    cohort, registration = _registered_cohort(
        organisation, name="Old group", is_active=False
    )

    response = _post(
        staff_client,
        _unregister_post_url(organisation, cohort),
        {"registration": str(registration.pk)},
    )

    registration.refresh_from_db()
    assert response.status_code == 422
    assert "to deactivate one of its course registrations." in " ".join(
        response.content.decode().split()
    )
    assert "Old group is inactive" in response.content.decode()
    assert registration.is_active is True


def _add_learners_url(organisation: Organisation, cohort: Cohort) -> str:
    return _cohort_url(
        organisation, cohort, "/__tabs/learners/__actions/add_existing_learners"
    )


def _learner_tab_triggers(client: Client, cohort: Cohort) -> list[str]:
    url = _cohort_url(cohort.organisation, cohort, "/__tabs/learners")
    document = lxml.html.fromstring(client.get(url).content.decode())
    return [
        button.get("hx-get") or ""
        for button in document.cssselect("button[hx-get]")
        if "add_existing_learners" in (button.get("hx-get") or "")
    ]


@pytest.mark.django_db
def test_a_cohort_admin_without_add_learner_sees_the_learner_picker_on_the_cohort_tab(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> None:
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    educator = _cohort_admin_on(organisation, cohort)

    triggers = _learner_tab_triggers(logged_in_client(educator), cohort)

    assert len(triggers) == 1


@pytest.mark.django_db
def test_an_organisation_admin_with_add_learner_sees_no_learner_picker(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> None:
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, educator, "organisation_admin", organisation)

    triggers = _learner_tab_triggers(logged_in_client(educator), cohort)

    assert triggers == []


@pytest.mark.django_db
def test_the_learner_picker_offers_learners_outside_the_cohort(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> None:
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    member = cast(Learner, LearnerFactory(organisation=organisation))
    CohortMembershipFactory(cohort=cohort, learner=member)
    outsider = cast(Learner, LearnerFactory(organisation=organisation))
    educator = _cohort_admin_on(organisation, cohort)
    CohortMembershipFactory(
        cohort=CohortFactory(organisation=organisation), learner=outsider
    )
    assign_role(
        LearnerFactory(user__superuser=True).user,
        educator,
        "organisation_admin",
        organisation,
    )

    offered = _offered_options(
        logged_in_client(educator), _add_learners_url(organisation, cohort)
    )

    assert str(member.pk) not in offered
    assert str(outsider.pk) in offered


@pytest.mark.django_db
def test_the_learner_picker_post_adds_each_learner(staff_client: Client) -> None:
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    first = cast(Learner, LearnerFactory(organisation=organisation))
    second = cast(Learner, LearnerFactory(organisation=organisation))

    response = staff_client.post(
        _add_learners_url(organisation, cohort),
        {"learners": [str(first.pk), str(second.pk)]},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 204
    assert set(
        CohortMembership.objects.filter(cohort=cohort).values_list(
            "learner_id", flat=True
        )
    ) == {first.pk, second.pk}


@pytest.mark.django_db
def test_the_learner_picker_post_sends_every_learner_id_and_the_cohort_id(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    first = cast(Learner, LearnerFactory(organisation=organisation))
    second = cast(Learner, LearnerFactory(organisation=organisation))

    response = staff_client.post(
        _add_learners_url(organisation, cohort),
        {"learners": [str(first.pk), str(second.pk)]},
        HTTP_HX_REQUEST="true",
    )

    trigger = json.loads(response["HX-Trigger"])
    assert set(trigger[LEARNER_CHANGED]["ids"]) == {str(first.pk), str(second.pk)}
    assert trigger[COHORT_CHANGED] == {"ids": [str(cohort.pk)]}


@pytest.mark.django_db
def test_a_stale_learner_picker_post_on_an_inactive_cohort_answers_422(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation, is_active=False))
    learner = cast(Learner, LearnerFactory(organisation=organisation))

    response = staff_client.post(
        _add_learners_url(organisation, cohort),
        {"learners": [str(learner.pk)]},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 422
    assert "to add learners to it." in " ".join(response.content.decode().split())
    assert not CohortMembership.objects.filter(cohort=cohort).exists()


def _add_learners_tab_url(organisation: Organisation, cohort: Cohort) -> str:
    return _cohort_url(organisation, cohort, "/__tabs/learners/__actions/add_learner")


@pytest.mark.django_db
def test_add_learner_post_on_a_cohort_tab_adds_to_that_cohort(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))

    response = _post(
        staff_client,
        _add_learners_tab_url(organisation, cohort),
        {"email": "new@example.com"},
    )

    assert response.status_code == 200
    assert cohort.cohortmembership_set.count() == 1


@pytest.mark.django_db
def test_the_cohort_tab_title_names_the_cohort(staff_client: Client) -> None:
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation, name="Wave One"))

    fragment = _get_fragment(staff_client, _add_learners_tab_url(organisation, cohort))

    assert "Add a learner to Wave One" in fragment


@pytest.mark.django_db
def test_an_organisation_admins_cohort_tab_offers_add_learners_not_the_picker(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> None:
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    client = logged_in_client(_organisation_admin_on(organisation))
    url = _cohort_url(organisation, cohort, "/__tabs/learners")

    document = lxml.html.fromstring(client.get(url).content.decode())

    hx_gets = [
        button.get("hx-get") or "" for button in document.cssselect("button[hx-get]")
    ]
    assert [g.rsplit("/", 1)[-1] for g in hx_gets if "__actions/add" in g] == [
        "add_learner"
    ]


@pytest.mark.django_db
def test_an_inactive_cohorts_tab_offers_no_add_learners(staff_client: Client) -> None:
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation, is_active=False))

    html = staff_client.get(
        _cohort_url(organisation, cohort, "/__tabs/learners")
    ).content.decode()

    assert "__actions/add_learner" not in html


@pytest.mark.django_db
def test_a_stale_add_learners_post_on_an_inactive_cohort_answers_422_and_adds_nothing(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation, is_active=False))

    response = _post(
        staff_client,
        _add_learners_tab_url(organisation, cohort),
        {"email": "new@example.com"},
    )

    assert response.status_code == 422
    assert "to add learners to it." in " ".join(response.content.decode().split())
    assert not Learner.objects.filter(user__email="new@example.com").exists()


@pytest.mark.django_db
def test_an_empty_learner_picker_says_everyone_is_already_in_the_cohort(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> None:
    organisation = OrganisationFactory()
    _, cohort = _membership(organisation, name="Cohort A")
    educator = _cohort_admin_on(organisation, cohort)

    text = _empty_picker_text(
        logged_in_client(educator), _add_learners_url(organisation, cohort)
    )

    assert (
        "Everyone in your other cohorts is already in Cohort A. To add someone new, "
        "ask an organisation admin." in text
    )


@pytest.mark.django_db
def test_a_stale_learner_picker_post_naming_a_member_answers_422_and_adds_nothing(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> None:
    organisation = OrganisationFactory()
    member, cohort = _membership(organisation)
    educator = _cohort_admin_on(organisation, cohort)

    response = logged_in_client(educator).post(
        _add_learners_url(organisation, cohort),
        {"learners": [str(member.pk)]},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 422
    assert CohortMembership.objects.filter(learner=member).count() == 1


@pytest.mark.django_db
def test_adding_existing_learners_writes_one_entry_per_learner(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> None:
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    first = cast(Learner, LearnerFactory(organisation=organisation))
    second = cast(Learner, LearnerFactory(organisation=organisation))
    actor = UserFactory(superuser=True)

    logged_in_client(actor).post(
        _add_learners_url(organisation, cohort),
        {"learners": [str(first.pk), str(second.pk)]},
        HTTP_HX_REQUEST="true",
    )

    entries = AuditLogEntry.unscoped.all()
    assert {(e.action, e.actor, e.target_object_id) for e in entries} == {
        ("cohort_membership.added", actor, str(first.pk)),
        ("cohort_membership.added", actor, str(second.pk)),
    }


@pytest.mark.django_db
def test_registering_a_cohort_writes_an_entry_by_the_logged_in_user(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> None:
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 0)
    actor = UserFactory(superuser=True)

    _post(
        logged_in_client(actor),
        _register_url(organisation, cohort),
        {"course": str(CourseFactory().pk)},
    )

    entry = AuditLogEntry.unscoped.get()
    assert (entry.action, entry.actor) == ("cohort_registration.added", actor)


@pytest.mark.django_db
def test_unregistering_a_cohort_writes_an_entry_by_the_logged_in_user(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> None:
    organisation = OrganisationFactory()
    cohort, registration = _registered_cohort(organisation)
    actor = UserFactory(superuser=True)

    _post(
        logged_in_client(actor),
        _unregister_post_url(organisation, cohort),
        {"registration": str(registration.pk)},
    )

    entry = AuditLogEntry.unscoped.get()
    assert (entry.action, entry.actor) == ("cohort_registration.deactivated", actor)


@pytest.mark.django_db
def test_renaming_a_cohort_writes_an_entry_with_the_old_and_new_name(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> None:
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation, name="Old name"))
    actor = UserFactory(superuser=True)

    _post(
        logged_in_client(actor),
        _cohort_url(organisation, cohort, "/__actions/edit"),
        {"name": "New name"},
    )

    assert_entry(
        action="cohort.renamed",
        actor=actor,
        target=cohort,
        target_label="New name",
        organisation=organisation,
        details={"old": "Old name", "new": "New name"},
    )


@pytest.mark.django_db
def test_saving_a_cohort_under_its_own_name_writes_nothing(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation, name="Same"))

    response = _post(
        staff_client,
        _cohort_url(organisation, cohort, "/__actions/edit"),
        {"name": "Same"},
    )

    assert response.status_code == 204
    assert not AuditLogEntry.unscoped.exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("action_name", "code", "start_active"),
    [
        ("deactivate", "cohort.deactivated", True),
        ("reactivate", "cohort.reactivated", False),
    ],
)
def test_changing_a_cohorts_state_writes_an_entry(
    mock_site_context: Site,
    logged_in_client: Callable[[AbstractBaseUser], Client],
    action_name: str,
    code: str,
    start_active: bool,
) -> None:
    organisation = OrganisationFactory()
    cohort = cast(
        Cohort,
        CohortFactory(
            organisation=organisation, name="Evening", is_active=start_active
        ),
    )
    actor = UserFactory(superuser=True)

    _post(
        logged_in_client(actor),
        _cohort_url(organisation, cohort, f"/__actions/{action_name}"),
    )

    assert_entry(
        action=code,
        actor=actor,
        target=cohort,
        target_label="Evening",
        organisation=organisation,
    )


@pytest.mark.django_db
def test_a_stale_state_change_on_an_inactive_cohort_writes_nothing(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation, is_active=False))

    response = _post(
        staff_client, _cohort_url(organisation, cohort, "/__actions/deactivate")
    )

    assert response.status_code == 422
    assert not AuditLogEntry.unscoped.exists()


@pytest.mark.django_db
def test_a_stale_learner_in_the_learner_picker_answers_422_without_the_id(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    stale = str(uuid.uuid4())

    response = staff_client.post(
        _add_learners_url(organisation, cohort),
        {"learners": [stale]},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 422
    assert "Choose a learner from the list." in _bulk_text(response)
    assert stale not in response.content.decode()


@pytest.mark.django_db
def test_an_inactive_cohort_refusal_is_a_message_dialog(staff_client: Client) -> None:
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 1, is_active=False)

    response = _post(
        staff_client, _cohort_url(organisation, cohort, "/__actions/deactivate")
    )

    _assert_message_dialog(
        response,
        f"{cohort} is already inactive",
        "Nothing changed. Someone else may have deactivated it already.",
    )


@pytest.mark.django_db
def test_an_already_active_cohort_refusal_is_a_message_dialog(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 1)

    response = _post(
        staff_client, _cohort_url(organisation, cohort, "/__actions/reactivate")
    )

    _assert_message_dialog(
        response,
        f"{cohort} is already active",
        "Nothing changed. Someone else may have reactivated it already.",
    )


@pytest.mark.django_db
@pytest.mark.parametrize(("row", "registered"), REGISTERABLE_ROWS)
def test_registering_a_cohort_for_a_course_works_only_when_it_is_registerable(
    staff_client: Client, row: str, registered: bool
) -> None:
    organisation = OrganisationFactory()
    courses = course_per_reach_row(organisation)
    cohort = cast(Cohort, CohortFactory(organisation=organisation))

    response = _post(
        staff_client,
        _register_url(organisation, cohort),
        {"course": str(courses[row].pk)},
    )

    assert (
        response.status_code,
        CohortCourseRegistration.objects.filter(
            cohort=cohort, course=courses[row]
        ).exists(),
    ) == ((204 if registered else 422), registered)
