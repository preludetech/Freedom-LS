"""The educator's learner journey: the learners list, a learner's page and its
Courses tab, with a layout check at every QA viewport."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from django.contrib.auth.base_user import AbstractBaseUser
from django.utils import timezone

from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    TopicFactory,
)
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.role_assignment import assign_role
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.reports.tests.helpers import (
    form_progress,
    quiz_form,
    topic_progress,
)
from freedom_ls.tests.playwright_helpers import (
    QA_VIEWPORTS,
    assert_no_horizontal_overflow,
)

from .helpers import interface_url

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]


def test_opening_a_learner_and_their_courses_tab(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    page = educator_logged_in_page
    organisation = OrganisationFactory(name="Org A")
    learner = LearnerFactory(
        organisation=organisation,
        user__first_name="Ada",
        user__last_name="Lovelace",
        user__email="ada@example.com",
    )
    LearnerCourseRegistrationFactory(
        learner=learner, course=CourseFactory(title="Algebra")
    )
    grantor = LearnerFactory(user__superuser=True).user
    assign_role(grantor, educator_user, "organisation_admin", organisation)

    page.goto(interface_url(live_server, organisation.slug, "learners"))
    list_url = page.url
    page.get_by_role("link", name="Ada Lovelace").first.click()

    expect(page.locator("#instance-title")).to_have_text("Ada Lovelace")
    expect(page.get_by_text("ada@example.com").first).to_be_visible()
    page.get_by_role("link", name="Courses", exact=True).click()
    expect(page.get_by_text("Algebra")).to_be_visible()
    expect(page.get_by_text("Nothing completed yet")).to_be_visible()
    learner_url = page.url

    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        page.goto(list_url)
        assert_no_horizontal_overflow(page)
        page.goto(learner_url)
        assert_no_horizontal_overflow(page)


def test_the_courses_tab_card_with_an_attempts_table_fits_every_viewport(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    page = educator_logged_in_page
    organisation = OrganisationFactory(name="Org A")
    learner = LearnerFactory(organisation=organisation)
    course = CourseFactory(title="Algebra")
    quiz = quiz_form("Unit quiz", 50)
    ContentCollectionItemFactory(collection_object=course, child_object=quiz, order=0)
    LearnerCourseRegistrationFactory(learner=learner, course=course)
    # The commit hooks of a transaction=True test have already minted the record.
    record = CourseProgress.objects.get(learner=learner, course=course)
    form_progress(
        record,
        quiz,
        completed_time=timezone.now(),
        scores={"score": 1, "max_score": 2},
    )
    grantor = LearnerFactory(user__superuser=True).user
    assign_role(grantor, educator_user, "organisation_admin", organisation)

    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        page.goto(
            interface_url(
                live_server, organisation.slug, f"learners/{learner.pk}/__tabs/courses"
            )
        )
        expect(page.get_by_text("1 of 1 items")).to_be_visible()
        expect(page.get_by_text("Passed", exact=True)).to_be_visible()
        assert_no_horizontal_overflow(page)


def test_deactivating_then_reactivating_a_learner_from_the_page_header(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    page = educator_logged_in_page
    organisation = OrganisationFactory(name="Org A")
    learner = LearnerFactory(
        organisation=organisation,
        user__first_name="Ada",
        user__last_name="Lovelace",
    )
    grantor = LearnerFactory(user__superuser=True).user
    assign_role(grantor, educator_user, "organisation_admin", organisation)
    page.goto(interface_url(live_server, organisation.slug, f"learners/{learner.pk}"))
    modal = page.locator("#app-modal")
    main = page.locator("#main-content")

    main.get_by_role("button", name="Deactivate", exact=True).first.click()
    modal.get_by_role("button", name="Deactivate", exact=True).click()

    expect(modal).to_be_hidden()
    expect(main.get_by_text("Removed", exact=True).first).to_be_visible()
    main.get_by_role("button", name="Reactivate", exact=True).first.click()
    modal.get_by_role("button", name="Reactivate", exact=True).click()
    expect(modal).to_be_hidden()
    expect(main.get_by_text("Active", exact=True).first).to_be_visible()


def test_moving_a_learner_between_cohorts_carries_their_progress(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    page = educator_logged_in_page
    organisation = OrganisationFactory(name="Org A")
    learner = LearnerFactory(
        organisation=organisation,
        user__first_name="Ada",
        user__last_name="Lovelace",
    )
    course = CourseFactory(title="Algebra")
    done_topic = TopicFactory()
    open_topic = TopicFactory()
    ContentCollectionItemFactory(
        collection_object=course, child_object=done_topic, order=0
    )
    ContentCollectionItemFactory(
        collection_object=course, child_object=open_topic, order=1
    )
    source = CohortFactory(organisation=organisation, name="Morning group")
    destination = CohortFactory(organisation=organisation, name="Evening group")
    CohortMembershipFactory(cohort=source, learner=learner)
    CohortCourseRegistrationFactory(cohort=source, course=course)
    CohortCourseRegistrationFactory(cohort=destination, course=course)
    # The commit hooks of a transaction=True test have already minted the record.
    CourseProgress.objects.filter(learner=learner, course=course).update(
        progress_percentage=40
    )
    topic_progress(
        CourseProgress.objects.get(learner=learner, course=course),
        done_topic,
        complete_time=timezone.now(),
    )
    grantor = LearnerFactory(user__superuser=True).user
    assign_role(grantor, educator_user, "organisation_admin", organisation)
    page.goto(interface_url(live_server, organisation.slug, f"learners/{learner.pk}"))
    modal = page.locator("#app-modal")
    main = page.locator("#main-content")

    main.get_by_role("button", name="Move", exact=True).first.click()
    modal.locator("select[name='destination']").select_option(label="Evening group")
    expect(modal.get_by_text("Algebra: continues at 40%")).to_be_visible()
    modal.get_by_role("button", name="Move", exact=True).click()

    expect(modal).to_be_hidden()
    expect(main.get_by_text("Evening group").first).to_be_visible()
    expect(main.get_by_text("Morning group")).to_have_count(0)
    page.get_by_role("link", name="Courses", exact=True).click()
    expect(main.get_by_text("1 of 2 items")).to_be_visible()


def test_a_deactivation_reason_shows_on_the_learner_history_and_the_audit_log(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    page = educator_logged_in_page
    organisation = OrganisationFactory(name="Org A")
    learner = LearnerFactory(
        organisation=organisation,
        user__first_name="Ada",
        user__last_name="Lovelace",
    )
    grantor = LearnerFactory(user__superuser=True).user
    assign_role(grantor, educator_user, "organisation_admin", organisation)
    reason = "abcdefghij" * 50
    page.goto(interface_url(live_server, organisation.slug, f"learners/{learner.pk}"))
    modal = page.locator("#app-modal")
    main = page.locator("#main-content")

    main.get_by_role("button", name="Deactivate", exact=True).first.click()
    modal.get_by_label("Reason (optional)").fill(reason)
    modal.get_by_role("button", name="Deactivate", exact=True).click()

    expect(modal).to_be_hidden()
    expect(main.get_by_text("Removed", exact=True).first).to_be_visible()
    page.get_by_role("link", name="History", exact=True).click()
    history_row = main.get_by_role("row").filter(has_text="Learner deactivated")
    expect(history_row).to_have_count(1)
    expect(history_row.get_by_text(reason)).to_be_visible()
    # A long unbroken reason wraps inside the Details cell instead of
    # stretching the table past its scroll wrapper.
    table = main.get_by_role("table")
    assert table.evaluate("t => t.offsetWidth <= t.parentElement.clientWidth"), (
        "the History table is wider than its wrapper"
    )
    page.goto(interface_url(live_server, organisation.slug, "audit-log"))
    row = main.get_by_role("row").filter(has_text="Learner deactivated")
    expect(row.get_by_text("Ada Lovelace").first).to_be_visible()
    expect(row.get_by_text(reason)).to_be_visible()
    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        page.goto(interface_url(live_server, organisation.slug, "audit-log"))
        assert_no_horizontal_overflow(page)
