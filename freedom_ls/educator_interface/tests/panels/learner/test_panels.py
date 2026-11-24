"""The learner page's panels: educator_interface/panels/learner/panels.py.

The Courses panel's cards and register trigger, and the Settings tab's name and
account panels.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

import lxml.html
import pytest

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
    TopicFactory,
)
from freedom_ls.educator_interface.tests.helpers import (
    _get_document,
    _interface_url,
    _learner_page,
    _org_admin,
    _region_text,
    _shared_and_own_course_world,
    _shared_by_notes,
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
        path = f"learners/{learner.pk}/__tabs/courses/__panels/courses"

        response = client.get(
            reverse(
                "educator_interface:interface",
                kwargs={
                    "organisation_slug": learner.organisation.slug,
                    "path_string": path,
                },
            )
        )

        document = lxml.html.fromstring(response.content.decode())
        (card_list,) = document.xpath("//ul[li//h3]")
        assert "list-none" in card_list.get("class").split()

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
        assert "2 of 2 items" in text
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
        row_link = document.cssselect("tbody tr")[number - 1].cssselect("a")[0]

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

        (card,) = document.cssselect("ul[data-row-cards] > li")
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
            with CaptureQueriesContext(connection) as queries:
                _courses_panel_html(client, learner.organisation.slug, learner)
            return len(queries)

        assert tab_queries(20) <= tab_queries(2)

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
        LearnerCourseRegistrationFactory(
            learner=learner, course=CourseFactory(title=title)
        )

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

    assert _shared_by_notes(document) == ["Shared by Northwind Logistics"]
