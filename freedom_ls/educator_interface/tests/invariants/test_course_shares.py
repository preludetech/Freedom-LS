"""What revoking a course share does and does not take away.

A course reaches an organisation through ownership, a share, or a registration
the organisation holds on it. Removing the organisation from `shared_with` and
reloading the content removes the share and nothing else: every registration
and progress record stays, and the course stays listed through the
registrations. Only the ways in that rest on the share go: the register
pickers, the content previews and reactivating a registration.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import pytest
from pytest_django.fixtures import DjangoAssertNumQueries

from django.contrib.sites.models import Site
from django.test import Client

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    TopicFactory,
)
from freedom_ls.content_engine.management.commands.content_save import (
    save_content_to_db,
)
from freedom_ls.content_engine.models import Course, CourseAudience
from freedom_ls.content_engine.tests.helpers import write_organisation_course
from freedom_ls.educator_interface.tests.helpers import (
    _content_action_url,
    organisation_admin_viewer,
)
from freedom_ls.educator_interface.tests.test_actions import (
    _learner_reregister_url,
    _post,
)
from freedom_ls.educator_interface.tests.test_views import (
    _export_csv,
    _interface_url,
    _learner_page,
)
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import (
    CohortCourseRegistration,
    Learner,
    LearnerCourseRegistration,
)
from freedom_ls.learner_management.queries import (
    COURSE_NOT_OPEN_MESSAGE,
    registerable_courses,
)
from freedom_ls.learner_progress.factories import CourseProgressFactory
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation

# The warm request count is 51 for both the one-course and ten-course lists. The test
# makes an unmeasured request first so per-process caches (content types, site, role
# configuration) are filled; the bound adds two queries of headroom.
QUERY_BOUND = 53
SHARED_FRONTMATTER = (
    "organisations:\n  - owner\nshared_with:\n  - sharee\naudience: public\n"
)
REVOKED_FRONTMATTER = "organisations:\n  - owner\naudience: public\n"


@dataclass
class RevokedShare:
    organisation: Organisation
    course: Course
    learner: Learner
    learner_registration: LearnerCourseRegistration
    cohort_registration: CohortCourseRegistration
    progress: CourseProgress


@pytest.fixture
def revoked_share(site: Site, mock_site_context: Site, tmp_path: Path) -> RevokedShare:
    """A course owned by one organisation and shared with another through
    `content_save`, which the sharee registers a cohort and a learner on and
    records progress against, then reloaded with the share removed."""
    OrganisationFactory(name="Owner", slug="owner")
    organisation = OrganisationFactory(name="Sharee", slug="sharee")
    course_file = write_organisation_course(tmp_path, SHARED_FRONTMATTER)
    save_content_to_db(tmp_path, site.name)
    course = Course.objects.get(site=site, title="Org Course")
    cohort_registration = CohortCourseRegistrationFactory(
        cohort=CohortFactory(organisation=organisation), course=course
    )
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    learner_registration = LearnerCourseRegistrationFactory(
        learner=learner, course=course, is_active=False
    )
    progress = CourseProgressFactory(
        learner=learner, course=course, learner_registration=learner_registration
    )

    course_file.write_text(f"""---
content_type: COURSE
title: Org Course
uuid: 70000000-0000-0000-0000-000000000001
{REVOKED_FRONTMATTER}---
""")
    save_content_to_db(tmp_path, site.name)

    return RevokedShare(
        organisation,
        course,
        learner,
        learner_registration,
        cohort_registration,
        progress,
    )


@pytest.mark.django_db
def test_revoking_a_share_keeps_the_registrations_and_the_progress(
    revoked_share: RevokedShare,
):
    assert revoked_share.course.shared_with.count() == 0
    assert LearnerCourseRegistration.objects.filter(
        pk=revoked_share.learner_registration.pk
    ).exists()
    assert CohortCourseRegistration.objects.filter(
        pk=revoked_share.cohort_registration.pk
    ).exists()
    assert CourseProgress.objects.filter(pk=revoked_share.progress.pk).exists()


@pytest.mark.django_db
def test_revoking_a_share_keeps_the_course_listed_through_its_registrations(
    revoked_share: RevokedShare, logged_in_client: Callable[[User], Client]
):
    client = logged_in_client(organisation_admin_viewer(revoked_share.organisation))

    response = client.get(_interface_url(revoked_share.organisation.slug, "courses"))

    assert str(revoked_share.course.pk) in response.content.decode()


@pytest.mark.django_db
def test_revoking_a_share_removes_the_course_from_the_register_pickers(
    revoked_share: RevokedShare,
):
    choices = registerable_courses(revoked_share.organisation)

    assert revoked_share.course.pk not in [course.pk for course in choices]


@pytest.mark.django_db
@pytest.mark.parametrize("action", ["preview_content", "preview_course_details"])
def test_revoking_a_share_makes_the_content_previews_answer_404(
    revoked_share: RevokedShare,
    logged_in_client: Callable[[User], Client],
    action: str,
):
    item = ContentCollectionItemFactory(
        collection_object=revoked_share.course, child_object=TopicFactory(), order=0
    )
    client = logged_in_client(organisation_admin_viewer(revoked_share.organisation))
    url = _content_action_url(revoked_share.organisation, revoked_share.course, action)

    response = client.get(f"{url}?item={item.pk}", HTTP_HX_REQUEST="true")

    assert response.status_code == 404


@pytest.mark.django_db
def test_revoking_a_share_makes_reactivating_a_registration_on_it_answer_422(
    revoked_share: RevokedShare, logged_in_client: Callable[[User], Client]
):
    client = logged_in_client(organisation_admin_viewer(revoked_share.organisation))

    response = _post(
        client,
        _learner_reregister_url(revoked_share.organisation, revoked_share.learner),
        {"registration": str(revoked_share.learner_registration.pk)},
    )

    assert response.status_code == 422
    assert COURSE_NOT_OPEN_MESSAGE in response.content.decode()


@pytest.mark.django_db
def test_revoking_a_share_takes_the_reactivate_trigger_off_the_registrations_card(
    revoked_share: RevokedShare, logged_in_client: Callable[[User], Client]
):
    client = logged_in_client(organisation_admin_viewer(revoked_share.organisation))

    document = _learner_page(client, revoked_share.learner, "overview")

    (row,) = [
        row
        for row in document.cssselect("[data-testid='registration-row']")
        if "Individual" in row.text_content()
    ]
    assert "Reactivate" not in row.text_content()


@pytest.mark.django_db
def test_an_inactive_registration_on_an_available_course_still_offers_reactivate(
    mock_site_context: Site, logged_in_client: Callable[[User], Client]
):
    organisation = OrganisationFactory()
    course = cast(Course, CourseFactory(audience=CourseAudience.PUBLIC))
    course.organisations.add(OrganisationFactory())
    course.shared_with.add(organisation)
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    LearnerCourseRegistrationFactory(learner=learner, course=course, is_active=False)
    client = logged_in_client(organisation_admin_viewer(organisation))

    document = _learner_page(client, learner, "overview")

    (row,) = document.cssselect("[data-testid='registration-row']")
    assert "Reactivate" in row.text_content()


@pytest.mark.django_db
def test_the_learners_export_names_who_shares_a_shared_course(
    mock_site_context: Site, logged_in_client: Callable[[User], Client]
):
    organisation = OrganisationFactory()
    own = cast(Course, CourseFactory(title="Safety"))
    own.organisations.add(organisation)
    shared = cast(Course, CourseFactory(title="Safety", slug="safety-shared"))
    shared.organisations.add(OrganisationFactory(name="Northwind"))
    shared.shared_with.add(organisation)
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    LearnerCourseRegistrationFactory(learner=learner, course=own)
    LearnerCourseRegistrationFactory(learner=learner, course=shared)
    client = logged_in_client(organisation_admin_viewer(organisation))

    _header, rows, _disposition = _export_csv(client, "learners", organisation)

    (row,) = rows
    assert sorted(row[4].split(", ")) == ["Safety", "Safety (Northwind)"]


def _share_courses(organisation: Organisation, count: int) -> None:
    for _ in range(count):
        course = cast(Course, CourseFactory(audience=CourseAudience.PUBLIC))
        course.organisations.add(OrganisationFactory())
        course.shared_with.add(organisation)


@pytest.mark.django_db
def test_the_courses_list_query_count_does_not_grow_with_shared_courses(
    mock_site_context: Site,
    logged_in_client: Callable[[User], Client],
    django_assert_max_num_queries: DjangoAssertNumQueries,
):
    organisation = OrganisationFactory()
    client = logged_in_client(organisation_admin_viewer(organisation))
    url = _interface_url(organisation.slug, "courses")
    _share_courses(organisation, 1)
    client.get(url)  # warm-up: fills per-process caches, not measured
    with django_assert_max_num_queries(QUERY_BOUND):
        assert client.get(url).status_code == 200
    _share_courses(organisation, 9)

    with django_assert_max_num_queries(QUERY_BOUND):
        response = client.get(url)

    assert response.status_code == 200
