"""The learner quick view: educator_interface/panels/learner/quick_view.py.

An htmx GET of `learners/<pk>/__quick-view` returns the drawer's frame with the
learner's memberships, registrations and message box, scoped the same way the
learners list and instance pages are.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

import pytest
from lxml import html

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

if TYPE_CHECKING:
    # Stub-only: the test client's response carries `templates`, which a plain
    # HttpResponse does not.
    pass

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.comms.factories import ConversationFactory, MessageFactory
from freedom_ls.comms.messaging_policy import (
    MessagingDecision,
    MessagingPolicy,
    MessagingRefusal,
)
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import Course
from freedom_ls.educator_interface.events import LEARNER_CHANGED
from freedom_ls.educator_interface.panels.learner.quick_view import LearnerQuickView
from freedom_ls.educator_interface.tests.helpers import _get_quick_view, _quick_view_url
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import Learner
from freedom_ls.learner_progress.factories import CourseProgressFactory
from freedom_ls.learner_progress.utils import ensure_course_progress_record
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation


@pytest.fixture(autouse=True)
def _site_context(mock_site_context):
    """Every test here builds site-aware objects and assigns roles."""


@pytest.mark.django_db
class TestLearnerQuickView:
    def test_shows_the_learners_name_and_email(self, role_holder_client):
        organisation = OrganisationFactory()
        learner = cast(
            Learner,
            LearnerFactory(
                user=UserFactory(
                    first_name="Ada", last_name="Lovelace", email="ada@example.com"
                ),
                organisation=organisation,
            ),
        )

        response = _get_quick_view(
            role_holder_client(organisation), organisation, f"learners/{learner.pk}"
        )

        assert response.status_code == 200
        content = response.content.decode()
        assert "Ada Lovelace" in content
        assert "ada@example.com" in content

    def test_titles_the_drawer_with_the_learners_display_name(self, role_holder_client):
        organisation = OrganisationFactory()
        learner = cast(
            Learner,
            LearnerFactory(
                user=UserFactory(first_name="Ada", last_name="Lovelace"),
                organisation=organisation,
            ),
        )

        response = _get_quick_view(
            role_holder_client(organisation), organisation, f"learners/{learner.pk}"
        )

        assert 'data-quick-view-title="Ada Lovelace"' in response.content.decode()

    def test_shows_the_learners_status_as_a_toned_badge(self, role_holder_client):
        organisation = OrganisationFactory()
        learner = cast(
            Learner, LearnerFactory(organisation=organisation, is_active=False)
        )

        response = _get_quick_view(
            role_holder_client(organisation), organisation, f"learners/{learner.pk}"
        )

        (badge,) = html.fromstring(response.content).cssselect("[data-tone]")
        assert badge.text_content().strip() == "Inactive"
        assert badge.get("data-tone") == "muted"

    def test_subtitles_the_drawer_with_the_learners_email(self, role_holder_client):
        organisation = OrganisationFactory()
        learner = cast(
            Learner,
            LearnerFactory(
                user=UserFactory(
                    first_name="Ada", last_name="Lovelace", email="ada@example.com"
                ),
                organisation=organisation,
            ),
        )

        response = _get_quick_view(
            role_holder_client(organisation), organisation, f"learners/{learner.pk}"
        )

        assert 'data-quick-view-subtitle="ada@example.com"' in response.content.decode()

    def test_shows_active_status_for_an_active_learner(self, role_holder_client):
        organisation = OrganisationFactory()
        learner = LearnerFactory(organisation=organisation, is_active=True)

        response = _get_quick_view(
            role_holder_client(organisation), organisation, f"learners/{learner.pk}"
        )

        assert "Active" in response.content.decode()

    def test_shows_pending_status_for_a_learner_who_has_never_logged_in(
        self, role_holder_client
    ):
        organisation = OrganisationFactory()
        learner = LearnerFactory(organisation=organisation, is_active=True)
        learner.user.set_unusable_password()
        learner.user.save(update_fields=["password"])

        response = _get_quick_view(
            role_holder_client(organisation), organisation, f"learners/{learner.pk}"
        )

        assert "Pending" in response.content.decode()

    def test_lists_a_visible_cohort_membership_as_a_link(self, role_holder_client):
        organisation = OrganisationFactory()
        learner = LearnerFactory(organisation=organisation)
        cohort = CohortFactory(organisation=organisation, name="Year 9 Maths")
        CohortMembershipFactory(learner=learner, cohort=cohort)

        response = _get_quick_view(
            role_holder_client(organisation), organisation, f"learners/{learner.pk}"
        )

        content = response.content.decode()
        assert "Year 9 Maths" in content
        assert f"cohorts/{cohort.pk}" in content

    def test_cohort_link_is_bold_like_a_person_link(self, role_holder_client):
        """The quick view's cohort names used to be medium weight, not bold."""
        organisation = OrganisationFactory()
        learner = LearnerFactory(organisation=organisation)
        cohort = CohortFactory(organisation=organisation, name="Year 9 Maths")
        CohortMembershipFactory(learner=learner, cohort=cohort)

        response = _get_quick_view(
            role_holder_client(organisation), organisation, f"learners/{learner.pk}"
        )

        document = html.fromstring(response.content.decode())
        links = document.xpath(f"//a[contains(@href, 'cohorts/{cohort.pk}')]")
        assert links
        assert all("font-bold" in link.get("class") for link in links)

    def test_shows_a_course_registration_through_a_cohort_with_its_progress(
        self, role_holder_client
    ):
        organisation = OrganisationFactory()
        learner = LearnerFactory(organisation=organisation)
        cohort = CohortFactory(organisation=organisation, name="Year 9 Maths")
        CohortMembershipFactory(learner=learner, cohort=cohort)
        course: Course = CourseFactory(title="Intro to Freedom")
        registration = CohortCourseRegistrationFactory(cohort=cohort, course=course)
        record = ensure_course_progress_record(learner, course, registration)
        record.progress_percentage = 55
        record.save(update_fields=["progress_percentage"])

        response = _get_quick_view(
            role_holder_client(organisation), organisation, f"learners/{learner.pk}"
        )

        document = html.fromstring(response.content.decode())
        (row,) = document.cssselect("[data-testid='quick-view-registration']")
        parts = [" ".join(e.text_content().split()) for e in row.cssselect("span, p")]
        assert parts == ["Intro to Freedom", "via Year 9 Maths", "55%"]

    def test_shows_no_progress_yet_for_a_registration_with_no_record(
        self, role_holder_client
    ):
        organisation = OrganisationFactory()
        learner = LearnerFactory(organisation=organisation)
        LearnerCourseRegistrationFactory(
            learner=learner, course=CourseFactory(title="Untouched Course")
        )

        response = _get_quick_view(
            role_holder_client(organisation), organisation, f"learners/{learner.pk}"
        )

        content = response.content.decode()
        assert "Untouched Course" in content
        assert "No progress yet" in content

    def test_shows_never_for_a_learner_with_no_progress_records(
        self, role_holder_client
    ):
        organisation = OrganisationFactory()
        learner = LearnerFactory(
            organisation=organisation, user=UserFactory(last_active=None)
        )

        response = _get_quick_view(
            role_holder_client(organisation), organisation, f"learners/{learner.pk}"
        )

        assert "Never" in response.content.decode()

    def test_last_active_is_the_users_not_the_latest_course_activity(
        self, role_holder_client
    ):
        organisation = OrganisationFactory()
        learner = LearnerFactory(
            organisation=organisation,
            user=UserFactory(last_active=datetime(2020, 1, 2, 9, 0, tzinfo=UTC)),
        )
        CourseProgressFactory(learner=learner, last_accessed_time=timezone.now())

        response = _get_quick_view(
            role_holder_client(organisation), organisation, f"learners/{learner.pk}"
        )

        assert "2 Jan 2020" in response.content.decode()

    def test_a_learner_in_another_organisation_404s(self, role_holder_client):
        organisation = OrganisationFactory()
        outside_learner = LearnerFactory(organisation=OrganisationFactory())

        response = _get_quick_view(
            role_holder_client(organisation),
            organisation,
            f"learners/{outside_learner.pk}",
        )

        assert response.status_code == 404

    def test_a_malformed_pk_404s(self, role_holder_client):
        organisation = OrganisationFactory()

        response = _get_quick_view(
            role_holder_client(organisation), organisation, "learners/not-a-uuid"
        )

        assert response.status_code == 404

    def test_a_non_htmx_get_redirects_to_the_instance_page(self, role_holder_client):
        organisation = OrganisationFactory()
        learner = LearnerFactory(organisation=organisation)

        response = role_holder_client(organisation).get(
            _quick_view_url(organisation.slug, f"learners/{learner.pk}")
        )

        assert response.status_code == 302
        assert response["Location"] == reverse(
            "educator_interface:interface",
            kwargs={
                "organisation_slug": organisation.slug,
                "path_string": f"learners/{learner.pk}",
            },
        )

    def test_response_varies_on_hx_request(self, role_holder_client):
        organisation = OrganisationFactory()
        learner = LearnerFactory(organisation=organisation)

        response = _get_quick_view(
            role_holder_client(organisation), organisation, f"learners/{learner.pk}"
        )

        assert "HX-Request" in response["Vary"]

    def test_an_instructor_scoped_to_one_cohort_does_not_see_a_membership_elsewhere(
        self, role_holder_client
    ):
        organisation = OrganisationFactory()
        granted_cohort = CohortFactory(organisation=organisation, name="Granted")
        other_cohort = CohortFactory(organisation=organisation, name="Elsewhere")
        learner = LearnerFactory(organisation=organisation)
        CohortMembershipFactory(learner=learner, cohort=granted_cohort)
        CohortMembershipFactory(learner=learner, cohort=other_cohort)

        response = _get_quick_view(
            role_holder_client(granted_cohort, "cohort_admin"),
            organisation,
            f"learners/{learner.pk}",
        )

        content = response.content.decode()
        assert "Granted" in content
        assert "Elsewhere" not in content

    def test_an_instructor_scoped_to_one_cohort_does_not_see_a_registration_elsewhere(
        self, role_holder_client
    ):
        organisation = OrganisationFactory()
        granted_cohort = CohortFactory(organisation=organisation, name="Granted")
        other_cohort = CohortFactory(organisation=organisation, name="Elsewhere")
        learner = LearnerFactory(organisation=organisation)
        CohortMembershipFactory(learner=learner, cohort=granted_cohort)
        CohortMembershipFactory(learner=learner, cohort=other_cohort)
        CohortCourseRegistrationFactory(
            cohort=granted_cohort, course=CourseFactory(title="Granted Course")
        )
        CohortCourseRegistrationFactory(
            cohort=other_cohort, course=CourseFactory(title="Hidden Course")
        )
        LearnerCourseRegistrationFactory(
            learner=learner, course=CourseFactory(title="Individual Course")
        )

        response = _get_quick_view(
            role_holder_client(granted_cohort, "cohort_admin"),
            organisation,
            f"learners/{learner.pk}",
        )

        content = response.content.decode()
        assert "Granted Course" in content
        assert "Individual Course" in content
        assert "Hidden Course" not in content
        assert "Elsewhere" not in content


@pytest.mark.django_db
def test_the_learners_list_renders_the_quick_view_trigger_attributes(
    role_holder_client,
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(
        organisation=organisation, user=UserFactory(first_name="Ada")
    )

    response = role_holder_client(organisation).get(
        reverse(
            "educator_interface:interface",
            kwargs={"organisation_slug": organisation.slug, "path_string": "learners"},
        )
    )

    content = response.content.decode()
    expected_url = _quick_view_url(organisation.slug, f"learners/{learner.pk}")
    assert f'hx-get="{expected_url}"' in content
    assert 'aria-controls="quick-view"' in content


class _AllowPolicy(MessagingPolicy):
    def can_start(self, *, sender, recipient, site):
        return MessagingDecision.allow()

    def can_reply(self, *, sender, recipient, site, conversation):
        return MessagingDecision.allow()

    def recipients_for(self, *, sender, site):
        return User.objects.exclude(pk=sender.pk)


class _ClosedPolicy(_AllowPolicy):
    def can_start(self, *, sender, recipient, site):
        return MessagingDecision.refuse(MessagingRefusal.CLOSED_BY_CONFIGURATION)

    def can_reply(self, *, sender, recipient, site, conversation):
        return MessagingDecision.refuse(MessagingRefusal.CLOSED_BY_CONFIGURATION)


@pytest.fixture
def messaging_on(settings) -> None:
    settings.MESSAGING_ENABLED = True
    settings.MESSAGING_POLICY = f"{__name__}._AllowPolicy"


@pytest.fixture
def messaging_closed(settings) -> None:
    settings.MESSAGING_ENABLED = True
    settings.MESSAGING_POLICY = f"{__name__}._ClosedPolicy"


def _learner_in(organisation: Organisation) -> Learner:
    return cast(
        Learner,
        LearnerFactory(
            user=UserFactory(first_name="Ada", last_name="Lovelace"),
            organisation=organisation,
        ),
    )


def _educator_with_conversation(
    role_holder_client, organisation: Organisation, learner: Learner, bodies: list[str]
):
    """A client for a new educator who already talks to ``learner``."""
    client = role_holder_client(organisation)
    educator = User.objects.get(pk=client.session["_auth_user_id"])
    conversation = ConversationFactory(between=(educator, learner.user))
    for body in bodies:
        MessageFactory(conversation=conversation, sender=learner.user, body=body)
    return client, conversation


@pytest.mark.django_db
@pytest.mark.usefixtures("messaging_on")
class TestLearnerQuickViewMessageBox:
    def test_the_send_button_is_a_small_icon_only_ghost_button(
        self, role_holder_client
    ):
        """The quick view is narrow, so Send is an icon named by its label."""
        organisation = OrganisationFactory()
        learner = _learner_in(organisation)

        response = _get_quick_view(
            role_holder_client(organisation), organisation, f"learners/{learner.pk}"
        )

        tree = html.fromstring(f"<div>{response.content.decode()}</div>")
        (send,) = tree.xpath("//form[@id='composer']//button[@type='submit']")
        classes = set(send.get("class").split())
        assert {"btn-ghost", "btn-sm"} <= classes
        assert send.get("aria-label") == "Send"
        assert send.text_content().strip() == ""
        assert send.xpath(".//svg[@data-icon='send']")
        assert "Organisation admins can read" not in tree.text_content()

    def test_the_messages_heading_sits_above_a_rule_with_room_below(
        self, role_holder_client
    ):
        organisation = OrganisationFactory()
        learner = _learner_in(organisation)

        response = _get_quick_view(
            role_holder_client(organisation), organisation, f"learners/{learner.pk}"
        )

        tree = html.fromstring(f"<div>{response.content.decode()}</div>")
        (heading,) = tree.xpath("//h3[@id='quick-view-message-heading']")
        row = heading.getparent()
        assert {"border-b", "pb-3", "mb-4"} <= set(row.get("class").split())
        assert "mt-6" in row.getparent().get("class").split()

    def test_the_composer_draws_no_rule_of_its_own_under_the_messages_heading(
        self, role_holder_client
    ):
        """The heading row already draws the section's rule; a second one on
        the composer stacked two rules a few pixels apart."""
        organisation = OrganisationFactory()
        learner = _learner_in(organisation)

        response = _get_quick_view(
            role_holder_client(organisation), organisation, f"learners/{learner.pk}"
        )

        tree = html.fromstring(f"<div>{response.content.decode()}</div>")
        (form,) = tree.xpath("//form[@id='composer']")
        assert "border-t" not in form.get("class").split()

    def test_shows_the_composer_when_there_is_no_conversation_yet(
        self, role_holder_client
    ):
        organisation = OrganisationFactory()
        learner = _learner_in(organisation)

        response = _get_quick_view(
            role_holder_client(organisation), organisation, f"learners/{learner.pk}"
        )

        tree = html.fromstring(f"<div>{response.content.decode()}</div>")
        box = tree.xpath("//div[@id='quick-view-message-box']")[0]
        form = box.xpath(".//form[@id='composer']")[0]
        assert form.get("hx-post") == reverse("conversations:start")
        assert form.get("hx-target") == "#quick-view-message-box"
        assert form.get("hx-swap") == "outerHTML"
        assert form.xpath(".//input[@name='recipient']")[0].get("value") == str(
            learner.user.pk
        )

    def test_lists_the_last_three_messages_and_links_to_the_conversation(
        self, role_holder_client
    ):
        organisation = OrganisationFactory()
        learner = _learner_in(organisation)
        client, conversation = _educator_with_conversation(
            role_holder_client,
            organisation,
            learner,
            ["first", "second", "third", "fourth"],
        )

        response = _get_quick_view(client, organisation, f"learners/{learner.pk}")

        content = response.content.decode()
        tree = html.fromstring(f"<div>{content}</div>")
        box = tree.xpath("//div[@id='quick-view-message-box']")[0]
        assert "first" not in box.text_content()
        for body in ("second", "third", "fourth"):
            assert body in box.text_content()
        form = box.xpath(".//form[@id='composer']")[0]
        assert form.get("hx-post") == reverse(
            "conversations:send", kwargs={"pk": conversation.pk}
        )
        link = tree.xpath("//a[normalize-space()='Open conversation']")[0]
        assert link.get("href").endswith(f"/learners/{learner.pk}/__tabs/messages")

    def test_the_open_conversation_link_points_at_the_tab_before_a_conversation_exists(
        self, role_holder_client
    ):
        organisation = OrganisationFactory()
        learner = _learner_in(organisation)

        response = _get_quick_view(
            role_holder_client(organisation), organisation, f"learners/{learner.pk}"
        )

        tree = html.fromstring(f"<div>{response.content.decode()}</div>")
        link = tree.xpath("//a[normalize-space()='Open conversation']")[0]
        assert link.get("href").endswith(f"/learners/{learner.pk}/__tabs/messages")
        assert not tree.xpath("//*[@x-data='messageBox']")

    def test_leaves_refresh_events_unchanged(self):
        assert LearnerQuickView.refresh_events == (LEARNER_CHANGED,)


@pytest.mark.django_db
class TestLearnerQuickViewMessageBoxHidden:
    @pytest.mark.usefixtures("messaging_closed")
    def test_shows_no_box_when_the_policy_refuses(self, role_holder_client):
        organisation = OrganisationFactory()
        learner = _learner_in(organisation)
        client, _ = _educator_with_conversation(
            role_holder_client, organisation, learner, ["hello"]
        )

        response = _get_quick_view(client, organisation, f"learners/{learner.pk}")

        content = response.content.decode()
        assert "quick-view-message-box" not in content
        assert "Open conversation" not in content

    @pytest.mark.usefixtures("messaging_closed")
    def test_shows_no_box_when_a_first_message_is_refused(self, role_holder_client):
        organisation = OrganisationFactory()
        learner = _learner_in(organisation)

        response = _get_quick_view(
            role_holder_client(organisation), organisation, f"learners/{learner.pk}"
        )

        assert "quick-view-message-box" not in response.content.decode()

    def test_shows_no_box_and_runs_no_messaging_query_when_messaging_is_off(
        self, role_holder_client, settings
    ):
        settings.MESSAGING_ENABLED = False
        organisation = OrganisationFactory()
        learner = _learner_in(organisation)
        client = role_holder_client(organisation)

        with CaptureQueriesContext(connection) as queries:
            response = _get_quick_view(client, organisation, f"learners/{learner.pk}")

        assert response.status_code == 200
        assert "quick-view-message-box" not in response.content.decode()
        assert not [q["sql"] for q in queries if "comms_" in q["sql"]]


@pytest.mark.django_db
def test_a_nameless_learners_quick_view_is_titled_by_their_email(role_holder_client):
    organisation = OrganisationFactory()
    learner = cast(
        Learner,
        LearnerFactory(
            user=UserFactory(first_name="", last_name="", email="nameless@example.com"),
            organisation=organisation,
        ),
    )

    response = _get_quick_view(
        role_holder_client(organisation), organisation, f"learners/{learner.pk}"
    )

    assert 'data-quick-view-title="nameless@example.com"' in response.content.decode()


@pytest.mark.django_db
def test_a_quick_view_of_a_learner_from_another_organisation_answers_the_dialog(
    role_holder_client,
):
    organisation = OrganisationFactory()
    elsewhere = cast(Learner, LearnerFactory(organisation=OrganisationFactory()))

    response = _get_quick_view(
        role_holder_client(organisation), organisation, f"learners/{elsewhere.pk}"
    )

    assert response.status_code == 404
    assert "This is no longer available" in response.content.decode()


@pytest.mark.django_db
def test_a_quick_view_of_an_unknown_learner_answers_the_dialog(role_holder_client):
    organisation = OrganisationFactory()

    response = _get_quick_view(
        role_holder_client(organisation), organisation, f"learners/{uuid.uuid4()}"
    )

    assert response.status_code == 404
    assert "This is no longer available" in response.content.decode()


def _register_on_shared_course(learner: Learner, organisation: Organisation) -> None:
    course = cast(Course, CourseFactory())
    course.organisations.add(OrganisationFactory())
    course.shared_with.add(organisation)
    LearnerCourseRegistrationFactory(learner=learner, course=course)


@pytest.mark.django_db
def test_a_learner_quick_view_query_count_does_not_grow_with_shared_registrations(
    role_holder_client,
):
    organisation = OrganisationFactory()
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    client = role_holder_client(organisation)
    path_string = f"learners/{learner.pk}"
    _register_on_shared_course(learner, organisation)
    _get_quick_view(client, organisation, path_string)  # warm per-process caches
    with CaptureQueriesContext(connection) as one_course:
        _get_quick_view(client, organisation, path_string)
    for _ in range(4):
        _register_on_shared_course(learner, organisation)

    with CaptureQueriesContext(connection) as five_courses:
        response = _get_quick_view(client, organisation, path_string)

    assert response.status_code == 200
    assert len(five_courses) == len(one_course)
