"""The learner page's panels: educator_interface/panels/learner/panels.py.

The Courses panel's cards and register trigger, and the Settings tab's name and
account panels.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

import lxml.html
import pytest

from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    CoursePartFactory,
    TopicFactory,
)
from freedom_ls.educator_interface.tests.helpers import (
    FAILED_QUIZ_REASON,
    IDLE_REASON,
    _get_document,
    _interface_url,
    _learner_page,
    _org_admin,
    _region_text,
    _shared_and_own_course_world,
    _shared_by_notes,
    cohort_with_idle_and_failed_learners,
    organisation_admin_viewer,
)
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_progress.tests.helpers import course_progress_record
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.reports.tests.helpers import (
    form_progress,
    quiz_form,
    topic_progress,
)
from freedom_ls.role_based_permissions.utils import assign_object_role


@pytest.fixture(autouse=True)
def _site_context(mock_site_context):
    """Every test here builds site-aware objects and assigns roles."""


def _courses_panel_html(client: Client, organisation_slug: str, learner: object) -> str:
    response = client.get(
        reverse(
            "educator_interface:interface",
            kwargs={
                "organisation_slug": organisation_slug,
                "path_string": f"learners/{learner.pk}/__tabs/courses/__panels/courses",
            },
        )
    )
    assert response.status_code == 200
    return str(response.content.decode())


def _courses_panel(client: Client, organisation_slug: str, learner: object) -> str:
    return " ".join(
        lxml.html.fromstring(_courses_panel_html(client, organisation_slug, learner))
        .text_content()
        .split()
    )


@pytest.mark.django_db
class TestLearnerCoursesPanel:
    def test_a_registration_through_a_cohort_the_viewer_cannot_see_is_hidden(
        self, logged_in_client
    ):
        organisation = OrganisationFactory()
        learner = LearnerFactory(organisation=organisation)
        visible = CohortFactory(organisation=organisation, name="Visible group")
        hidden = CohortFactory(organisation=organisation, name="Hidden group")
        CohortMembershipFactory(cohort=visible, learner=learner)
        CohortMembershipFactory(cohort=hidden, learner=learner)
        CohortCourseRegistrationFactory(
            cohort=visible, course=CourseFactory(title="Algebra")
        )
        CohortCourseRegistrationFactory(
            cohort=hidden, course=CourseFactory(title="Secret Course")
        )
        educator = UserFactory(staff=True)
        assign_object_role(educator, visible, "cohort_admin")

        text = _courses_panel(logged_in_client(educator), organisation.slug, learner)

        assert "Algebra" in text
        assert "via Visible group" in text
        assert "Secret Course" not in text
        assert "Hidden group" not in text

    def test_the_course_cards_are_ordered_by_title_whatever_the_registration_kind(
        self, logged_in_client
    ):
        learner = LearnerFactory()
        LearnerCourseRegistrationFactory(
            learner=learner, course=CourseFactory(title="Zoology")
        )
        cohort = CohortFactory(organisation=learner.organisation)
        CohortMembershipFactory(cohort=cohort, learner=learner)
        CohortCourseRegistrationFactory(
            cohort=cohort, course=CourseFactory(title="Algebra")
        )

        text = _courses_panel(
            logged_in_client(_org_admin(learner.organisation)),
            learner.organisation.slug,
            learner,
        )

        assert text.index("Algebra") < text.index("Zoology")

    def test_the_course_cards_list_shows_no_list_markers(self, logged_in_client):
        """The theme bullets bare lists, so each course card had a stray marker."""
        learner = LearnerFactory()
        LearnerCourseRegistrationFactory(learner=learner, course=CourseFactory())
        client = logged_in_client(_org_admin(learner.organisation))

        document = lxml.html.fromstring(
            _courses_panel_html(client, learner.organisation.slug, learner)
        )

        (card_list,) = document.cssselect("ul[data-row-cards]")
        assert "list-none" in card_list.get("class").split()

    def test_two_registrations_render_two_rows_under_the_five_column_headings(
        self, logged_in_client
    ):
        learner = LearnerFactory()
        for title in ("Algebra", "Geometry"):
            LearnerCourseRegistrationFactory(
                learner=learner, course=CourseFactory(title=title)
            )
        client = logged_in_client(_org_admin(learner.organisation))

        document = lxml.html.fromstring(
            _courses_panel_html(client, learner.organisation.slug, learner)
        )

        (table,) = document.cssselect("table")
        headings = [th.text_content().strip() for th in table.cssselect("thead th")]
        assert headings == ["Course", "Status", "Progress", "Items", "Last completed"]
        assert len(table.cssselect("tbody tr")) == 2

    def test_the_courses_table_has_a_caption_naming_the_learner(self, logged_in_client):
        learner = LearnerFactory()
        LearnerCourseRegistrationFactory(learner=learner, course=CourseFactory())
        client = logged_in_client(_org_admin(learner.organisation))

        document = lxml.html.fromstring(
            _courses_panel_html(client, learner.organisation.slug, learner)
        )

        (caption,) = document.cssselect("table caption")
        assert caption.text_content().strip() == (
            f"Courses for {learner.user.display_name}"
        )

    def test_each_registration_is_also_a_card_with_the_same_labelled_values(
        self, logged_in_client
    ):
        learner = LearnerFactory()
        for title in ("Algebra", "Geometry"):
            LearnerCourseRegistrationFactory(
                learner=learner, course=CourseFactory(title=title)
            )
        client = logged_in_client(_org_admin(learner.organisation))

        document = lxml.html.fromstring(
            _courses_panel_html(client, learner.organisation.slug, learner)
        )

        cards = document.cssselect("ul[data-row-cards] > li")
        assert len(cards) == 2
        labels = [dt.text_content().strip() for dt in cards[0].cssselect("dt")]
        assert labels == ["Status", "Progress", "Items", "Last completed"]
        assert "Algebra" in cards[0].text_content()

    def test_the_course_cell_holds_the_title_and_how_the_learner_is_registered(
        self, logged_in_client
    ):
        learner = LearnerFactory()
        LearnerCourseRegistrationFactory(
            learner=learner, course=CourseFactory(title="Algebra")
        )
        client = logged_in_client(_org_admin(learner.organisation))

        document = lxml.html.fromstring(
            _courses_panel_html(client, learner.organisation.slug, learner)
        )

        cell = document.cssselect("tbody tr td")[0]
        assert " ".join(cell.text_content().split()) == "Algebra Individual"

    def test_the_progress_cell_names_its_bar_after_the_course(self, logged_in_client):
        learner = LearnerFactory()
        LearnerCourseRegistrationFactory(
            learner=learner, course=CourseFactory(title="Algebra")
        )
        client = logged_in_client(_org_admin(learner.organisation))

        document = lxml.html.fromstring(
            _courses_panel_html(client, learner.organisation.slug, learner)
        )

        (bar,) = document.cssselect("tbody progress")
        assert bar.get("aria-label") == "Algebra progress"

    def test_the_progress_bar_has_a_fixed_width_so_a_wide_status_cell_cannot_squeeze_it(
        self, logged_in_client
    ):
        """The bar sat bare in an auto-sized column and shrank to about 22px
        beside the Status column's flag reason sentence."""
        learner = LearnerFactory()
        LearnerCourseRegistrationFactory(
            learner=learner, course=CourseFactory(title="Algebra")
        )
        client = logged_in_client(_org_admin(learner.organisation))

        document = lxml.html.fromstring(
            _courses_panel_html(client, learner.organisation.slug, learner)
        )

        (bar,) = document.cssselect("tbody progress")
        wrapper = bar.getparent().getparent()
        assert "w-32" in wrapper.get("class", "").split()

    def test_the_items_cell_reads_completed_of_total(self, logged_in_client):
        course = CourseFactory(title="Algebra")
        done = TopicFactory()
        ContentCollectionItemFactory(
            collection_object=course, child_object=done, order=0
        )
        ContentCollectionItemFactory(
            collection_object=course, child_object=TopicFactory(), order=1
        )
        record = course_progress_record(course, UserFactory())
        topic_progress(record, done, complete_time=timezone.now())
        learner = record.learner
        client = logged_in_client(_org_admin(learner.organisation))

        document = lxml.html.fromstring(
            _courses_panel_html(client, learner.organisation.slug, learner)
        )

        items_cell = document.cssselect("tbody tr td")[3]
        assert items_cell.text_content().strip() == "1 of 2"

    def test_the_last_completed_cell_names_the_item_and_the_date(
        self, logged_in_client
    ):
        course = CourseFactory(title="Algebra")
        topic = TopicFactory(title="Fractions")
        ContentCollectionItemFactory(
            collection_object=course, child_object=topic, order=0
        )
        record = course_progress_record(course, UserFactory())
        topic_progress(record, topic, complete_time=timezone.now())
        learner = record.learner
        client = logged_in_client(_org_admin(learner.organisation))

        document = lxml.html.fromstring(
            _courses_panel_html(client, learner.organisation.slug, learner)
        )

        last_cell = document.cssselect("tbody tr td")[4]
        assert last_cell.text_content().strip().startswith("Fractions, ")

    def test_a_course_with_a_quiz_result_gets_a_section_after_the_table(
        self, logged_in_client
    ):
        course = CourseFactory(title="Algebra")
        quiz = quiz_form("Unit quiz", 50)
        ContentCollectionItemFactory(
            collection_object=course, child_object=quiz, order=0
        )
        record = course_progress_record(course, UserFactory())
        form_progress(
            record,
            quiz,
            completed_time=timezone.now(),
            scores={"score": 2, "max_score": 2},
        )
        learner = record.learner
        client = logged_in_client(_org_admin(learner.organisation))

        document = lxml.html.fromstring(
            _courses_panel_html(client, learner.organisation.slug, learner)
        )

        (section,) = document.cssselect("section[aria-labelledby]")
        assert section.cssselect("h3")[0].text_content().strip() == "Algebra"
        assert section.cssselect("table caption")[0].text_content().strip() == (
            "Unit quiz attempts"
        )

    def test_a_quiz_heading_is_set_smaller_than_its_course_heading(
        self, logged_in_client
    ):
        """The quiz h4 used to carry the course h3's size, so each quiz read as a
        sibling section of its course instead of part of it."""
        course = CourseFactory(title="Algebra")
        quiz = quiz_form("Unit quiz", 50)
        ContentCollectionItemFactory(
            collection_object=course, child_object=quiz, order=0
        )
        record = course_progress_record(course, UserFactory())
        form_progress(
            record,
            quiz,
            completed_time=timezone.now(),
            scores={"score": 2, "max_score": 2},
        )
        learner = record.learner
        client = logged_in_client(_org_admin(learner.organisation))

        document = lxml.html.fromstring(
            _courses_panel_html(client, learner.organisation.slug, learner)
        )

        (section,) = document.cssselect("section[aria-labelledby]")
        quiz_classes = section.cssselect("h4")[0].get("class").split()
        assert "text-base" in quiz_classes
        assert "text-base" not in section.cssselect("h3")[0].get("class").split()

    def test_a_course_with_completed_items_gets_a_section_listing_them(
        self, logged_in_client
    ):
        course = CourseFactory(title="Algebra")
        topic = TopicFactory(title="Fractions")
        ContentCollectionItemFactory(
            collection_object=course, child_object=topic, order=0
        )
        record = course_progress_record(course, UserFactory())
        topic_progress(record, topic, complete_time=timezone.now())
        learner = record.learner
        client = logged_in_client(_org_admin(learner.organisation))

        document = lxml.html.fromstring(
            _courses_panel_html(client, learner.organisation.slug, learner)
        )

        (section,) = document.cssselect("section[aria-labelledby]")
        assert "Completed items (1)" in section.text_content()

    def test_a_course_with_neither_completed_items_nor_quiz_results_gets_no_section(
        self, logged_in_client
    ):
        learner = LearnerFactory()
        LearnerCourseRegistrationFactory(learner=learner, course=CourseFactory())
        client = logged_in_client(_org_admin(learner.organisation))

        document = lxml.html.fromstring(
            _courses_panel_html(client, learner.organisation.slug, learner)
        )

        assert not document.cssselect("section[aria-labelledby]")

    def test_a_learner_with_no_registrations_gets_the_empty_message(
        self, logged_in_client
    ):
        learner = LearnerFactory()
        client = logged_in_client(_org_admin(learner.organisation))

        text = _courses_panel(client, learner.organisation.slug, learner)

        assert "Not registered on any courses yet" in text

    def test_a_card_shows_items_completed_attempts_pass_mark_and_verdicts(
        self, logged_in_client
    ):
        course = CourseFactory(title="Algebra")
        topic = TopicFactory(title="Fractions")
        quiz = quiz_form("Unit quiz", 50)
        ContentCollectionItemFactory(
            collection_object=course, child_object=topic, order=0
        )
        ContentCollectionItemFactory(
            collection_object=course, child_object=quiz, order=1
        )
        user = UserFactory()
        record = course_progress_record(course, user)
        topic_progress(record, topic, complete_time=timezone.now())
        form_progress(
            record,
            quiz,
            completed_time=timezone.now() - timedelta(days=1),
            scores={"score": 0, "max_score": 2},
        )
        form_progress(
            record,
            quiz,
            completed_time=timezone.now(),
            scores={"score": 2, "max_score": 2},
        )
        learner = record.learner
        client = logged_in_client(_org_admin(learner.organisation))

        text = _courses_panel(client, learner.organisation.slug, learner)

        assert "Individual" in text
        assert "Complete" in text
        assert "2 of 2" in text
        assert "Completed items (2)" in text
        assert "0/2 0% 50% Failed" in text
        assert "2/2 100% 50% Passed Latest" in text

    def test_a_quiz_without_a_pass_mark_says_so_and_shows_no_verdict(
        self, logged_in_client
    ):
        course = CourseFactory()
        quiz = quiz_form("Open quiz", None)
        ContentCollectionItemFactory(
            collection_object=course, child_object=quiz, order=0
        )
        record = course_progress_record(course, UserFactory())
        form_progress(
            record,
            quiz,
            completed_time=timezone.now(),
            scores={"score": 1, "max_score": 2},
        )
        client = logged_in_client(_org_admin(record.learner.organisation))

        text = _courses_panel(client, record.learner.organisation.slug, record.learner)

        assert "1/2 50% No pass mark Latest" in text
        assert "Passed" not in text
        assert "Failed" not in text

    def test_only_an_openable_sitting_has_its_attempt_number_as_a_quick_view_trigger(
        self,
        logged_in_client: Callable[[User], Client],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        course = CourseFactory(title="Algebra")
        quiz = quiz_form("Unit quiz", 50)
        ContentCollectionItemFactory(
            collection_object=course, child_object=quiz, order=0
        )
        record = course_progress_record(course, UserFactory())
        first = form_progress(
            record,
            quiz,
            completed_time=timezone.now() - timedelta(days=1),
            scores={"score": 0, "max_score": 2},
        )
        form_progress(
            record,
            quiz,
            completed_time=timezone.now(),
            scores={"score": 2, "max_score": 2},
        )
        monkeypatch.setattr(
            "freedom_ls.educator_interface.panels.learner.panels.openable_sitting_ids",
            lambda request, ids, shown_registrations=None: {first.pk},
        )
        learner = record.learner
        client = logged_in_client(_org_admin(learner.organisation))

        document = lxml.html.fromstring(
            _courses_panel_html(client, learner.organisation.slug, learner)
        )

        triggers = document.cssselect("tbody a[aria-controls='quick-view']")
        review_url = _interface_url(
            learner.organisation.slug, f"quiz-attempts/{first.pk}"
        )
        assert len(triggers) == 1
        assert triggers[0].get("href") == review_url
        assert triggers[0].get("hx-get") == f"{review_url}/__quick-view"
        assert triggers[0].text_content().strip() == "1"
        assert triggers[0].get("aria-label") == "Attempt 1 of Unit quiz"

    @pytest.mark.parametrize("number", [1, 2, 3])
    def test_each_attempt_number_opens_the_page_for_that_sitting(
        self, logged_in_client: Callable[[User], Client], number: int
    ) -> None:
        course = CourseFactory(title="Algebra")
        quiz = quiz_form("Unit quiz", 50)
        ContentCollectionItemFactory(
            collection_object=course, child_object=quiz, order=0
        )
        record = course_progress_record(course, UserFactory())
        now = timezone.now()
        for days in (3, 2, 1):
            form_progress(
                record,
                quiz,
                completed_time=now - timedelta(days=days),
                scores={"score": 1, "max_score": 2},
            )
        form_progress(record, quiz, scores={"score": 0, "max_score": 2})
        learner = record.learner
        client = logged_in_client(_org_admin(learner.organisation))
        document = lxml.html.fromstring(
            _courses_panel_html(client, learner.organisation.slug, learner)
        )
        attempts_table = document.cssselect("section[aria-labelledby] table")[0]
        row_link = attempts_table.cssselect("tbody tr")[number - 1].cssselect("a")[0]

        response = client.get(row_link.get("href"))

        assert response.status_code == 200
        heading = lxml.html.fromstring(response.content.decode()).cssselect(
            "#instance-title"
        )[0]
        assert heading.text_content().strip().endswith(f"attempt {number}")

    def test_the_attempts_table_also_renders_as_cards_with_the_same_trigger(
        self, logged_in_client: Callable[[User], Client]
    ) -> None:
        course = CourseFactory(title="Algebra")
        quiz = quiz_form("Unit quiz", 50)
        ContentCollectionItemFactory(
            collection_object=course, child_object=quiz, order=0
        )
        record = course_progress_record(course, UserFactory())
        form_progress(
            record,
            quiz,
            completed_time=timezone.now(),
            scores={"score": 2, "max_score": 2},
        )
        learner = record.learner
        client = logged_in_client(_org_admin(learner.organisation))

        document = lxml.html.fromstring(
            _courses_panel_html(client, learner.organisation.slug, learner)
        )

        (card,) = document.cssselect("section[aria-labelledby] ul[data-row-cards] > li")
        assert card.cssselect("a[aria-controls='quick-view']")
        card_text = " ".join(card.text_content().split())
        for label in ("Completed", "Score", "Percentage", "Pass mark", "Result"):
            assert label in card_text

    def test_the_tab_costs_no_more_queries_for_twenty_attempts_than_for_two(
        self, logged_in_client: Callable[[User], Client]
    ) -> None:
        def tab_queries(count: int) -> int:
            course = CourseFactory()
            quiz = quiz_form(f"Quiz of {count}", 50)
            ContentCollectionItemFactory(
                collection_object=course, child_object=quiz, order=0
            )
            record = course_progress_record(course, UserFactory())
            now = timezone.now()
            for index in range(count):
                form_progress(
                    record,
                    quiz,
                    completed_time=now - timedelta(minutes=count - index),
                    scores={"score": 1, "max_score": 2},
                )
            learner = record.learner
            client = logged_in_client(_org_admin(learner.organisation))
            # Both measurements start from a cold content-type cache, so the
            # first call does not pay a lookup the second one gets for free.
            ContentType.objects.clear_cache()
            with CaptureQueriesContext(connection) as queries:
                _courses_panel_html(client, learner.organisation.slug, learner)
            return len(queries)

        assert tab_queries(20) <= tab_queries(2)

    def test_the_tab_costs_the_same_queries_for_four_courses_as_for_one(
        self, logged_in_client: Callable[[User], Client]
    ) -> None:
        def tab_queries(course_count: int) -> int:
            user = UserFactory()
            for number in range(course_count):
                course = CourseFactory()
                part = CoursePartFactory()
                ContentCollectionItemFactory(
                    collection_object=course, child_object=part, order=0
                )
                ContentCollectionItemFactory(
                    collection_object=part, child_object=TopicFactory(), order=0
                )
                ContentCollectionItemFactory(
                    collection_object=part,
                    child_object=quiz_form(f"Quiz {course_count}-{number}", 50),
                    order=1,
                )
                ContentCollectionItemFactory(
                    collection_object=course, child_object=TopicFactory(), order=1
                )
                record = course_progress_record(course, user)
            learner = record.learner
            client = logged_in_client(_org_admin(learner.organisation))
            ContentType.objects.clear_cache()
            with CaptureQueriesContext(connection) as queries:
                _courses_panel_html(client, learner.organisation.slug, learner)
            return len(queries)

        assert tab_queries(4) <= tab_queries(1)

    def test_a_course_with_nothing_completed_says_so_and_flags_no_activity(
        self, logged_in_client
    ):
        learner = LearnerFactory()
        course = CourseFactory(title="Algebra")
        ContentCollectionItemFactory(
            collection_object=course, child_object=TopicFactory(), order=0
        )
        LearnerCourseRegistrationFactory(learner=learner, course=course)
        client = logged_in_client(_org_admin(learner.organisation))

        text = _courses_panel(client, learner.organisation.slug, learner)

        assert "Nothing completed yet" in text
        assert "Not started" in text
        assert "No recorded activity" in text


@pytest.mark.django_db
def test_the_learner_settings_tab_offers_every_learner_action_to_an_org_admin(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation)
    page_url = _interface_url(organisation.slug, f"learners/{learner.pk}")

    document = _get_document(staff_client, f"{page_url}/__tabs/settings")

    (name,) = document.cssselect("section[data-panel='name']")
    (account,) = document.cssselect("section[data-panel='account']")
    labels = [
        button.text_content().strip() for button in account.cssselect("footer .btn")
    ]
    # The name is a field with Save on its own panel. Resend setup email is
    # offered only while the learner is pending. Add to cohort and Register
    # for a course sit with the cohorts and the courses.
    assert name.cssselect("form#learner-name-form")
    assert labels == ["Deactivate"]


@pytest.mark.django_db
def test_the_settings_tab_name_section_shows_the_email_above_the_name_form(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation, user__email="ada@example.com")
    page_url = _interface_url(organisation.slug, f"learners/{learner.pk}")

    document = _get_document(staff_client, f"{page_url}/__tabs/settings")

    (name,) = document.cssselect("section[data-panel='name']")
    (row,) = name.cssselect("dl > div")
    (label,) = row.cssselect("dt")
    (value,) = row.cssselect("dd")
    (form,) = name.cssselect("form#learner-name-form")
    assert label.text_content().strip() == "Email"
    assert value.text_content().strip() == "ada@example.com"
    assert form not in row.iterancestors()
    assert row not in form.iterancestors()
    assert list(name.iter()).index(row) < list(name.iter()).index(form)


@pytest.mark.django_db
def test_a_refused_rename_swaps_only_the_form_and_the_panel_keeps_its_email(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation, user__email="ada@example.com")
    page_url = _interface_url(organisation.slug, f"learners/{learner.pk}")

    response = staff_client.post(
        f"{page_url}/__actions/edit_name",
        {"first_name": "x" * 201, "last_name": "Lovelace"},
        HTTP_HX_REQUEST="true",
    )

    fragment = response.content.decode()
    assert response.status_code == 422
    assert "learner-name-form" in fragment
    assert "ada@example.com" not in fragment
    document = _get_document(staff_client, f"{page_url}/__tabs/settings")
    (value,) = document.cssselect("section[data-panel='name'] dl dd")
    assert value.text_content().strip() == "ada@example.com"


@pytest.mark.django_db
def test_a_viewer_who_may_not_rename_the_learner_sees_no_name_panel_or_email_row(
    role_holder_client,
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation, user__email="ada@example.com")
    page_url = _interface_url(organisation.slug, f"learners/{learner.pk}")

    document = _get_document(
        role_holder_client(organisation), f"{page_url}/__tabs/settings"
    )

    assert not document.cssselect("section[data-panel='name']")
    assert not document.xpath("//dd[contains(., 'ada@example.com')]")


@pytest.mark.django_db
def test_register_for_a_course_sits_on_the_learners_courses_tab(staff_client: Client):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation)
    page_url = _interface_url(organisation.slug, f"learners/{learner.pk}")

    document = _get_document(staff_client, f"{page_url}/__tabs/courses")

    (panel,) = document.cssselect("section[data-panel='courses']")
    labels = [
        button.text_content().strip() for button in panel.cssselect("footer .btn")
    ]
    assert labels == ["Register for a course"]


@pytest.mark.django_db
def test_the_courses_tab_shows_the_recomputed_percentage_not_the_stored_one(
    staff_client: Client,
):
    course = CourseFactory(title="Algebra")
    done_topic = TopicFactory()
    open_topic = TopicFactory()
    ContentCollectionItemFactory(
        collection_object=course, child_object=done_topic, order=0
    )
    ContentCollectionItemFactory(
        collection_object=course, child_object=open_topic, order=1
    )
    record = course_progress_record(course, UserFactory(), progress_percentage=90)
    topic_progress(record, done_topic, complete_time=timezone.now())

    document = _learner_page(staff_client, record.learner, "courses")

    text = _region_text(document)
    assert "50%" in text
    assert "90%" not in text


@pytest.mark.django_db
def test_the_courses_tab_says_nothing_completed_for_a_registration_without_activity(
    staff_client: Client,
):
    learner = LearnerFactory(organisation=OrganisationFactory())
    LearnerCourseRegistrationFactory(
        learner=learner, course=CourseFactory(title="Algebra")
    )

    document = _learner_page(staff_client, learner, "courses")

    assert "Nothing completed yet" in _region_text(document)


@pytest.mark.django_db
def test_the_courses_tab_sets_each_course_out_as_a_plain_section_not_a_nested_card(
    staff_client: Client,
):
    """Each course sat in its own bordered card inside the panel's card."""
    learner = LearnerFactory(organisation=OrganisationFactory())
    for title in ("Algebra", "Geometry"):
        course = CourseFactory(title=title)
        topic = TopicFactory()
        ContentCollectionItemFactory(
            collection_object=course, child_object=topic, order=0
        )
        LearnerCourseRegistrationFactory(learner=learner, course=course)
        record = course_progress_record(course, learner.user)
        topic_progress(record, topic, complete_time=timezone.now())

    document = _learner_page(staff_client, learner, "courses")

    (panel,) = document.cssselect("section[data-panel='courses']")
    assert len(panel.cssselect(".panel-surface")) == 1
    headings = [h.text_content().strip() for h in panel.cssselect("h3.panel-heading")]
    assert sorted(headings) == ["Algebra", "Geometry"]


@pytest.mark.django_db
def test_learner_courses_tab_names_the_owner_of_a_shared_course_only(
    mock_site_context: Site, logged_in_client: Callable[[User], Client]
):
    """A course card on the learner's Courses tab titled a shared course with
    its bare title."""
    organisation, own, shared = _shared_and_own_course_world()
    learner = LearnerFactory(organisation=organisation)
    LearnerCourseRegistrationFactory(learner=learner, course=shared)
    LearnerCourseRegistrationFactory(learner=learner, course=own)
    client = logged_in_client(organisation_admin_viewer(organisation))

    document = _get_document(
        client,
        _interface_url(organisation.slug, f"learners/{learner.pk}/__tabs/courses"),
    )

    (table,) = document.cssselect("table")
    assert _shared_by_notes(table) == ["Shared by Northwind Logistics"]


@pytest.mark.django_db
class TestFlagReasonsOnTheCoursesTab:
    def test_an_idle_learner_shows_the_badge_without_its_reason(
        self, logged_in_client: Callable[[User], Client]
    ) -> None:
        cohort, idle, _failed = cohort_with_idle_and_failed_learners()
        client = logged_in_client(_org_admin(cohort.organisation))

        text = _courses_panel(client, cohort.organisation.slug, idle)

        assert "No recorded activity" in text
        assert IDLE_REASON not in text

    def test_a_learner_who_failed_a_quiz_shows_the_failed_quiz_reason(
        self, logged_in_client: Callable[[User], Client]
    ) -> None:
        cohort, _idle, failed = cohort_with_idle_and_failed_learners()
        client = logged_in_client(_org_admin(cohort.organisation))

        text = _courses_panel(client, cohort.organisation.slug, failed)

        assert FAILED_QUIZ_REASON in text
