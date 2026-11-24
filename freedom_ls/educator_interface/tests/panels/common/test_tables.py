"""The table messages and person cells every educator table shares."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

import pytest

from django.contrib.sites.models import Site
from django.template.loader import render_to_string
from django.test import RequestFactory

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.educator_interface.panels.audit_log.data_tables import (
    OrganisationAuditLogTable,
)
from freedom_ls.educator_interface.panels.cohort.data_table_panels import (
    CohortHistoryPanel,
)
from freedom_ls.educator_interface.panels.cohort.data_tables import (
    CohortCourseRegistrationDataTable,
    CohortDataTable,
    LearnerCohortDataTable,
)
from freedom_ls.educator_interface.panels.course.data_tables import (
    CourseCohortRegistrationDataTable,
    CourseDataTable,
    CourseLearnerRegistrationDataTable,
)
from freedom_ls.educator_interface.panels.learner.data_table_panels import (
    LearnerHistoryPanel,
)
from freedom_ls.educator_interface.panels.learner.data_tables import (
    CohortLearnerDataTable,
    LearnerDataTable,
)
from freedom_ls.educator_interface.panels.staff.data_tables import StaffDataTable
from freedom_ls.educator_interface.tests.helpers import (
    get_interface_page,
    organisation_admin_viewer,
    profile_picture_sources,
)
from freedom_ls.learner_management.factories import (
    CohortFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.role_assignment import assign_role
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.panel_framework.tables import DataTable

EDUCATOR_TABLES: list[type[DataTable]] = [
    LearnerDataTable,
    CohortLearnerDataTable,
    CohortDataTable,
    LearnerCohortDataTable,
    CourseDataTable,
    CohortCourseRegistrationDataTable,
    CourseCohortRegistrationDataTable,
    CourseLearnerRegistrationDataTable,
    StaffDataTable,
    OrganisationAuditLogTable,
]


@pytest.mark.parametrize("table", EDUCATOR_TABLES)
def test_the_first_use_message_is_a_sentence(table: type[DataTable]) -> None:
    assert table.empty_message.endswith(".")
    assert table.empty_message != DataTable.empty_message


@pytest.mark.parametrize("panel", [LearnerHistoryPanel, CohortHistoryPanel])
def test_a_history_panel_says_what_will_be_recorded(panel: type) -> None:
    assert panel.empty_message.endswith(".")
    assert panel.data_table.empty_no_results.endswith(".")


@pytest.mark.parametrize("table", EDUCATOR_TABLES)
def test_the_no_results_message_is_a_sentence(table: type[DataTable]) -> None:
    assert table.empty_no_results.endswith(".")


@pytest.mark.django_db
@pytest.mark.parametrize("table", EDUCATOR_TABLES)
def test_a_filter_in_play_offers_to_clear_it(
    table: type[DataTable], mock_site_context: Site
) -> None:
    html = render_to_string(
        "panel_framework/partials/table_empty.html",
        {
            "any_filter_set": True,
            "empty_no_results": table.empty_no_results,
            "empty_message": table.empty_message,
            "clear_changes": {},
            "clear_search_changes": {},
            "page_url": "/x/",
            "base_url": "/x/",
            "region_id": "r",
        },
        request=RequestFactory().get("/x/"),
    )

    assert table.empty_no_results in html
    assert table.empty_message not in html
    assert "Clear filters" in html


# Profile pictures on the learners table, course registrations table, cohort settings panel and audit log.

PictureSurface = Callable[[Organisation, User], str]


def _learners_table(organisation: Organisation, person: User) -> str:
    LearnerFactory(organisation=organisation, user=person)
    return get_interface_page(
        organisation, "learners", organisation_admin_viewer(organisation)
    )


def _registrations_table(organisation: Organisation, person: User) -> str:
    course = CourseFactory()
    learner = LearnerFactory(organisation=organisation, user=person)
    LearnerCourseRegistrationFactory(learner=learner, course=course, is_active=True)
    return get_interface_page(
        organisation,
        f"courses/{course.pk}/__tabs/overview/__panels/learners",
        organisation_admin_viewer(organisation),
    )


def _cohort_settings(organisation: Organisation, person: User) -> str:
    cohort = CohortFactory(organisation=organisation)
    assign_role(UserFactory(superuser=True), person, "cohort_admin", cohort)
    return get_interface_page(
        organisation,
        f"cohorts/{cohort.pk}/__tabs/settings",
        organisation_admin_viewer(organisation),
    )


PICTURE_SURFACES = [
    pytest.param(_learners_table, id="learners-table"),
    pytest.param(_registrations_table, id="course-registrations-table"),
    pytest.param(_cohort_settings, id="cohort-settings"),
]


@pytest.mark.django_db
@pytest.mark.usefixtures("mock_site_context")
@pytest.mark.parametrize("surface", PICTURE_SURFACES)
def test_a_person_with_a_picture_shows_it(surface: PictureSurface) -> None:
    person = cast(User, UserFactory(with_profile_picture=True))

    content = surface(OrganisationFactory(), person)

    assert person.profile_picture_url in profile_picture_sources(content)


@pytest.mark.django_db
@pytest.mark.usefixtures("mock_site_context")
@pytest.mark.parametrize("surface", PICTURE_SURFACES)
def test_a_person_without_a_picture_shows_initials_alone(
    surface: PictureSurface,
) -> None:
    content = surface(OrganisationFactory(), cast(User, UserFactory()))

    assert profile_picture_sources(content) == []
    assert 'src="None"' not in content
