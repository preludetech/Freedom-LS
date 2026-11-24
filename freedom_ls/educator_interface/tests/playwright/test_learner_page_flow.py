"""The educator's learner journey: the learners list, a learner's page and its
Courses tab, with a layout check at every QA viewport."""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect
from pytest_django.live_server_helper import LiveServer

from django.contrib.auth.base_user import AbstractBaseUser
from django.core.files.base import ContentFile
from django.utils import timezone

from freedom_ls.accounts.tests.profile_picture_samples import png_bytes
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
    assert_no_space_below_field_row,
)

from .helpers import interface_url

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]


def test_opening_a_learner_and_their_courses_tab(
    live_server: LiveServer,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    """Opening a learner from the list shows their Courses tab; the sidebar
    shows the educator's profile picture, then their initials once the file
    is gone; and at every viewport the pages do not overflow and the
    registration rows sit on the left edge of the Registrations heading (they
    used to be indented by the default list margin)."""
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

    educator_user.profile_picture.save("me.png", ContentFile(png_bytes()), save=True)

    page.goto(interface_url(live_server, organisation.slug, "learners"))
    list_url = page.url
    expect(page.locator("#sidebar-user img[data-profile-picture]")).to_be_visible()
    page.get_by_role("link", name="Ada Lovelace").first.click()

    expect(page.locator("#instance-title")).to_have_text("Ada Lovelace")
    expect(page.get_by_text("ada@example.com").first).to_be_visible()
    page.locator("#main-content").get_by_role(
        "link", name="Courses", exact=True
    ).click()
    expect(page.get_by_text("Algebra")).to_be_visible()
    expect(page.get_by_text("Nothing completed yet")).to_be_visible()
    learner_url = page.url

    stored = educator_user.profile_picture
    stored.storage.delete(stored.name)
    page.reload()
    sidebar_user = page.locator("#sidebar-user")
    expect(
        sidebar_user.first.get_by_text(educator_user.initials, exact=True)
    ).to_be_visible()
    expect(sidebar_user.locator("img[data-profile-picture]")).to_have_count(0)

    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        page.goto(list_url)
        assert_no_horizontal_overflow(page)
        page.goto(learner_url)
        assert_no_horizontal_overflow(page)

        page.goto(
            interface_url(live_server, organisation.slug, f"learners/{learner.pk}")
        )
        heading = page.get_by_role("heading", name="Registrations", exact=True)
        row = page.get_by_test_id("registration-row")
        expect(
            row, f"registration row not shown at {viewport['width']}px"
        ).to_be_visible()
        heading_box = heading.bounding_box()
        row_box = row.bounding_box()
        assert heading_box is not None
        assert row_box is not None
        heading_left = heading_box["x"]
        row_left = row_box["x"]
        # Within a pixel: sub-pixel rounding is not an indent.
        assert abs(row_left - heading_left) < 1, (
            f"registration row at x={row_left}, heading at x={heading_left} "
            f"at {viewport['width']}px"
        )


def test_the_courses_tab_card_with_an_attempts_table_fits_every_viewport(
    live_server: LiveServer,
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
        # The table and the card list both hold the verdict; one is hidden.
        expect(
            page.get_by_text("Passed", exact=True).locator("visible=true")
        ).to_be_visible()
        assert_no_horizontal_overflow(page)


def test_moving_a_learner_between_cohorts_carries_their_progress(
    live_server: LiveServer,
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

    main.get_by_role("button", name=re.compile(r"^Move from ")).first.click()
    modal.locator("select[name='destination']").select_option(label="Evening group")
    expect(modal.get_by_text("Algebra: continues at 40%")).to_be_visible()
    modal.get_by_role("button", name="Move", exact=True).click()

    expect(modal).to_be_hidden()
    expect(main.get_by_text("Evening group").first).to_be_visible()
    expect(main.get_by_text("Morning group")).to_have_count(0)
    main.get_by_role("link", name="Courses", exact=True).click()
    expect(main.get_by_text("1 of 2 items")).to_be_visible()


def test_learner_settings_flow(
    live_server: LiveServer,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    """An organisation admin deactivating a learner with a 500-character
    reason sees the Inactive badge, the reason in the History row detail
    (wrapped inside the table) and in the audit log as a table row and as a
    card on a phone, with no overflow at any viewport. Reactivating clears the
    badge and brings back the Deactivate button. For a superuser, the Settings
    tab's name form has no space below its field row."""
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
    settings_url = interface_url(
        live_server, organisation.slug, f"learners/{learner.pk}/__tabs/settings"
    )
    audit_log_url = interface_url(live_server, organisation.slug, "audit-log")
    page.goto(settings_url)
    modal = page.locator("#app-modal")
    main = page.locator("#main-content")
    header = page.locator("#instance-header")

    # Deactivate.
    expect(header.get_by_text("Active", exact=True)).to_have_count(0)
    main.get_by_role("button", name="Deactivate", exact=True).first.click()
    modal.get_by_label("Reason (optional)").fill(reason)
    modal.get_by_role("button", name="Deactivate", exact=True).click()

    # The header refreshes on the learner-changed event and shows the badge.
    expect(modal).to_be_hidden()
    expect(header.get_by_text("Inactive", exact=True)).to_be_visible()
    expect(main.get_by_text("Inactive", exact=True).first).to_be_visible()

    # History.
    page.get_by_role("link", name="History", exact=True).click()
    history_row = main.get_by_role("row").filter(has_text="Learner deactivated")
    expect(history_row).to_have_count(1)
    toggle = history_row.get_by_role("button", name="More about", exact=False)
    toggle.focus()
    page.keyboard.press("Enter")
    expect(toggle).to_have_attribute("aria-expanded", "true")
    expect(main.locator("tr[data-row-detail]").get_by_text(reason)).to_be_visible()
    expect(toggle).to_be_focused()
    # A long unbroken reason wraps inside the row detail instead of
    # stretching the table past its scroll wrapper.
    table = main.get_by_role("table")
    assert table.evaluate("t => t.offsetWidth <= t.parentElement.clientWidth"), (
        "the History table is wider than its wrapper"
    )

    # Audit log.
    page.goto(audit_log_url)
    row = main.get_by_role("row").filter(has_text="Learner deactivated")
    expect(row.get_by_text("Ada Lovelace").first).to_be_visible()
    row.get_by_role("button", name="More about", exact=False).click()
    expect(main.locator("tr[data-row-detail]").get_by_text(reason)).to_be_visible()
    page.set_viewport_size({"width": 375, "height": 800})
    page.goto(audit_log_url)
    card = main.locator("li").filter(has_text="Learner deactivated")
    card_toggle = card.get_by_role("button", name="More about", exact=False)
    card_toggle.click()
    expect(card_toggle).to_have_attribute("aria-expanded", "true")
    expect(card.get_by_text(reason)).to_be_visible()
    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        page.goto(audit_log_url)
        assert_no_horizontal_overflow(page)

    # Reactivate.
    page.goto(settings_url)
    main.get_by_role("button", name="Reactivate", exact=True).first.click()
    modal.get_by_role("button", name="Reactivate", exact=True).click()
    expect(modal).to_be_hidden()
    expect(header.get_by_text("Inactive", exact=True)).to_have_count(0)
    expect(
        main.get_by_role("button", name="Deactivate", exact=True).first
    ).to_be_visible()

    # Editing the learner's name changes their user, which only a superuser may do.
    educator_user.is_superuser = True
    educator_user.save()
    page.goto(settings_url)
    assert_no_space_below_field_row(page.locator("#learner-name-form"))
