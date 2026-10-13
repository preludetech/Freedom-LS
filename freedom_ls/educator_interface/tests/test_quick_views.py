"""The learner and cohort quick views: educator_interface/quick_views.py.

LearnerConfig and CohortConfig now declare a `quick_view`, so an htmx GET of
`<section>/<pk>/__quick-view` returns the drawer's frame with each consumer's
own fields, scoped the same way the section's own list and instance pages
already are.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest
from lxml import html

from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

if TYPE_CHECKING:
    # Stub-only: the test client's response carries `templates`, which a plain
    # HttpResponse does not.
    from django.test.client import _MonkeyPatchedWSGIResponse

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
from freedom_ls.educator_interface.quick_views import LearnerQuickView
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import Cohort, Learner
from freedom_ls.learner_progress.utils import ensure_course_progress_record
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.role_based_permissions.utils import assign_object_role


@pytest.fixture(autouse=True)
def _site_context(mock_site_context):
    """Every test here builds site-aware objects and assigns roles."""


@pytest.fixture
def educator_client(logged_in_client):
    """Factory: a logged-in staff educator holding ``role`` on ``target`` --
    the organisation for a role holder, a cohort for a grant-only educator."""

    def _make(
        target: Organisation | Cohort, role: str = "organisation_admin"
    ) -> Client:
        educator = UserFactory(staff=True)
        assign_object_role(educator, target, role)
        return cast(Client, logged_in_client(educator))

    return _make


def _quick_view_url(organisation_slug: str, path_string: str) -> str:
    return reverse(
        "educator_interface:interface",
        kwargs={
            "organisation_slug": organisation_slug,
            "path_string": f"{path_string}/__quick-view",
        },
    )


def _get_quick_view(
    client: Client, organisation: Organisation, path_string: str
) -> _MonkeyPatchedWSGIResponse:
    return client.get(
        _quick_view_url(organisation.slug, path_string), HTTP_HX_REQUEST="true"
    )


@pytest.mark.django_db
class TestLearnerQuickView:
    def test_shows_the_learners_name_and_email(self, educator_client):
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
            educator_client(organisation), organisation, f"learners/{learner.pk}"
        )

        assert response.status_code == 200
        content = response.content.decode()
        assert "Ada Lovelace" in content
        assert "ada@example.com" in content

    def test_titles_the_drawer_with_the_learners_display_name(self, educator_client):
        organisation = OrganisationFactory()
        learner = cast(
            Learner,
            LearnerFactory(
                user=UserFactory(first_name="Ada", last_name="Lovelace"),
                organisation=organisation,
            ),
        )

        response = _get_quick_view(
            educator_client(organisation), organisation, f"learners/{learner.pk}"
        )

        assert 'data-quick-view-title="Ada Lovelace"' in response.content.decode()

    def test_subtitles_the_drawer_with_the_learners_email(self, educator_client):
        organisation = OrganisationFactory()
        learner = cast(
            Learner,
            LearnerFactory(
                user=UserFactory(email="ada@example.com"), organisation=organisation
            ),
        )

        response = _get_quick_view(
            educator_client(organisation), organisation, f"learners/{learner.pk}"
        )

        assert 'data-quick-view-subtitle="ada@example.com"' in response.content.decode()

    def test_shows_active_status_for_an_active_learner(self, educator_client):
        organisation = OrganisationFactory()
        learner = LearnerFactory(organisation=organisation, is_active=True)

        response = _get_quick_view(
            educator_client(organisation), organisation, f"learners/{learner.pk}"
        )

        assert "Active" in response.content.decode()

    def test_shows_pending_status_for_a_learner_who_has_never_logged_in(
        self, educator_client
    ):
        organisation = OrganisationFactory()
        learner = LearnerFactory(organisation=organisation, is_active=True)
        learner.user.set_unusable_password()
        learner.user.save(update_fields=["password"])

        response = _get_quick_view(
            educator_client(organisation), organisation, f"learners/{learner.pk}"
        )

        assert "Pending" in response.content.decode()

    def test_lists_a_visible_cohort_membership_as_a_link(self, educator_client):
        organisation = OrganisationFactory()
        learner = LearnerFactory(organisation=organisation)
        cohort = CohortFactory(organisation=organisation, name="Year 9 Maths")
        CohortMembershipFactory(learner=learner, cohort=cohort)

        response = _get_quick_view(
            educator_client(organisation), organisation, f"learners/{learner.pk}"
        )

        content = response.content.decode()
        assert "Year 9 Maths" in content
        assert f"cohorts/{cohort.pk}" in content

    def test_shows_a_course_registration_through_a_cohort_with_its_progress(
        self, educator_client
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
            educator_client(organisation), organisation, f"learners/{learner.pk}"
        )

        content = response.content.decode()
        assert "Intro to Freedom" in content
        assert "Year 9 Maths" in content
        assert "55" in content

    def test_shows_no_progress_yet_for_a_registration_with_no_record(
        self, educator_client
    ):
        organisation = OrganisationFactory()
        learner = LearnerFactory(organisation=organisation)
        LearnerCourseRegistrationFactory(
            learner=learner, course=CourseFactory(title="Untouched Course")
        )

        response = _get_quick_view(
            educator_client(organisation), organisation, f"learners/{learner.pk}"
        )

        content = response.content.decode()
        assert "Untouched Course" in content
        assert "No progress yet" in content

    def test_shows_never_for_a_learner_with_no_progress_records(self, educator_client):
        organisation = OrganisationFactory()
        learner = LearnerFactory(organisation=organisation)

        response = _get_quick_view(
            educator_client(organisation), organisation, f"learners/{learner.pk}"
        )

        assert "Never" in response.content.decode()

    def test_a_learner_in_another_organisation_404s(self, educator_client):
        organisation = OrganisationFactory()
        outside_learner = LearnerFactory(organisation=OrganisationFactory())

        response = _get_quick_view(
            educator_client(organisation),
            organisation,
            f"learners/{outside_learner.pk}",
        )

        assert response.status_code == 404

    def test_a_malformed_pk_404s(self, educator_client):
        organisation = OrganisationFactory()

        response = _get_quick_view(
            educator_client(organisation), organisation, "learners/not-a-uuid"
        )

        assert response.status_code == 404

    def test_a_non_htmx_get_redirects_to_the_instance_page(self, educator_client):
        organisation = OrganisationFactory()
        learner = LearnerFactory(organisation=organisation)

        response = educator_client(organisation).get(
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

    def test_response_varies_on_hx_request(self, educator_client):
        organisation = OrganisationFactory()
        learner = LearnerFactory(organisation=organisation)

        response = _get_quick_view(
            educator_client(organisation), organisation, f"learners/{learner.pk}"
        )

        assert "HX-Request" in response["Vary"]

    def test_an_instructor_scoped_to_one_cohort_does_not_see_a_membership_elsewhere(
        self, educator_client
    ):
        organisation = OrganisationFactory()
        granted_cohort = CohortFactory(organisation=organisation, name="Granted")
        other_cohort = CohortFactory(organisation=organisation, name="Elsewhere")
        learner = LearnerFactory(organisation=organisation)
        CohortMembershipFactory(learner=learner, cohort=granted_cohort)
        CohortMembershipFactory(learner=learner, cohort=other_cohort)

        response = _get_quick_view(
            educator_client(granted_cohort, "cohort_admin"),
            organisation,
            f"learners/{learner.pk}",
        )

        content = response.content.decode()
        assert "Granted" in content
        assert "Elsewhere" not in content

    def test_an_instructor_scoped_to_one_cohort_does_not_see_a_registration_elsewhere(
        self, educator_client
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
            educator_client(granted_cohort, "cohort_admin"),
            organisation,
            f"learners/{learner.pk}",
        )

        content = response.content.decode()
        assert "Granted Course" in content
        assert "Individual Course" in content
        assert "Hidden Course" not in content
        assert "Elsewhere" not in content


@pytest.mark.django_db
class TestCohortQuickView:
    def test_shows_the_cohorts_name(self, educator_client):
        organisation = OrganisationFactory()
        cohort = CohortFactory(organisation=organisation, name="Year 9 Maths")

        response = _get_quick_view(
            educator_client(organisation), organisation, f"cohorts/{cohort.pk}"
        )

        assert response.status_code == 200
        assert "Year 9 Maths" in response.content.decode()

    def test_shows_the_learner_count(self, educator_client):
        organisation = OrganisationFactory()
        cohort = CohortFactory(organisation=organisation)
        CohortMembershipFactory(
            cohort=cohort, learner=LearnerFactory(organisation=organisation)
        )
        CohortMembershipFactory(
            cohort=cohort, learner=LearnerFactory(organisation=organisation)
        )

        response = _get_quick_view(
            educator_client(organisation), organisation, f"cohorts/{cohort.pk}"
        )

        assert "2" in response.content.decode()

    def test_reads_active_from_an_active_cohort(self, educator_client):
        organisation = OrganisationFactory()
        cohort = CohortFactory(organisation=organisation)

        response = _get_quick_view(
            educator_client(organisation), organisation, f"cohorts/{cohort.pk}"
        )

        assert "Inactive" not in response.content.decode()
        assert "Active" in response.content.decode()

    def test_reads_inactive_from_an_inactive_cohort(self, educator_client):
        organisation = OrganisationFactory()
        cohort = CohortFactory(organisation=organisation, is_active=False)

        response = _get_quick_view(
            educator_client(organisation), organisation, f"cohorts/{cohort.pk}"
        )

        assert "Inactive" in response.content.decode()

    def test_lists_its_registered_courses(self, educator_client):
        organisation = OrganisationFactory()
        cohort = CohortFactory(organisation=organisation)
        CohortCourseRegistrationFactory(
            cohort=cohort, course=CourseFactory(title="Intro to Freedom")
        )

        response = _get_quick_view(
            educator_client(organisation), organisation, f"cohorts/{cohort.pk}"
        )

        assert "Intro to Freedom" in response.content.decode()

    def test_a_cohort_in_another_organisation_404s(self, educator_client):
        organisation = OrganisationFactory()
        outside_cohort = CohortFactory(organisation=OrganisationFactory())

        response = _get_quick_view(
            educator_client(organisation), organisation, f"cohorts/{outside_cohort.pk}"
        )

        assert response.status_code == 404

    def test_a_non_htmx_get_redirects_to_the_instance_page(self, educator_client):
        organisation = OrganisationFactory()
        cohort = CohortFactory(organisation=organisation)

        response = educator_client(organisation).get(
            _quick_view_url(organisation.slug, f"cohorts/{cohort.pk}")
        )

        assert response.status_code == 302
        assert response["Location"] == reverse(
            "educator_interface:interface",
            kwargs={
                "organisation_slug": organisation.slug,
                "path_string": f"cohorts/{cohort.pk}",
            },
        )

    def test_response_varies_on_hx_request(self, educator_client):
        organisation = OrganisationFactory()
        cohort = CohortFactory(organisation=organisation)

        response = _get_quick_view(
            educator_client(organisation), organisation, f"cohorts/{cohort.pk}"
        )

        assert "HX-Request" in response["Vary"]


@pytest.mark.django_db
def test_a_course_quick_view_404s_since_courses_declare_none(educator_client):
    organisation = OrganisationFactory()
    course: Course = CourseFactory()

    response = _get_quick_view(
        educator_client(organisation), organisation, f"courses/{course.pk}"
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_the_learners_list_renders_the_quick_view_trigger_attributes(
    educator_client,
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(
        organisation=organisation, user=UserFactory(first_name="Ada")
    )

    response = educator_client(organisation).get(
        reverse(
            "educator_interface:interface",
            kwargs={"organisation_slug": organisation.slug, "path_string": "learners"},
        )
    )

    content = response.content.decode()
    expected_url = _quick_view_url(organisation.slug, f"learners/{learner.pk}")
    assert f'hx-get="{expected_url}"' in content
    assert 'aria-controls="quick-view"' in content


@pytest.mark.django_db
def test_the_cohorts_list_renders_the_quick_view_trigger_attributes(
    educator_client,
):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation, name="Year 9 Maths")

    response = educator_client(organisation).get(
        reverse(
            "educator_interface:interface",
            kwargs={"organisation_slug": organisation.slug, "path_string": "cohorts"},
        )
    )

    content = response.content.decode()
    expected_url = _quick_view_url(organisation.slug, f"cohorts/{cohort.pk}")
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
    educator_client, organisation: Organisation, learner: Learner, bodies: list[str]
):
    """A client for a new educator who already talks to ``learner``."""
    client = educator_client(organisation)
    educator = User.objects.get(pk=client.session["_auth_user_id"])
    conversation = ConversationFactory(between=(educator, learner.user))
    for body in bodies:
        MessageFactory(conversation=conversation, sender=learner.user, body=body)
    return client, conversation


@pytest.mark.django_db
@pytest.mark.usefixtures("messaging_on")
class TestLearnerQuickViewMessageBox:
    def test_shows_the_composer_when_there_is_no_conversation_yet(
        self, educator_client
    ):
        organisation = OrganisationFactory()
        learner = _learner_in(organisation)

        response = _get_quick_view(
            educator_client(organisation), organisation, f"learners/{learner.pk}"
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
        assert box.get("data-conversation-pk") == ""

    def test_lists_the_last_three_messages_and_links_to_the_conversation(
        self, educator_client
    ):
        organisation = OrganisationFactory()
        learner = _learner_in(organisation)
        client, conversation = _educator_with_conversation(
            educator_client,
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
        assert box.get("data-conversation-pk") == str(conversation.pk)
        form = box.xpath(".//form[@id='composer']")[0]
        assert form.get("hx-post") == reverse(
            "conversations:send", kwargs={"pk": conversation.pk}
        )
        link = tree.xpath("//a[normalize-space()='Open conversation']")[0]
        assert link.get("href").endswith(f"/messages/{conversation.pk}")

    def test_the_open_conversation_link_has_no_target_before_a_conversation_exists(
        self, educator_client
    ):
        organisation = OrganisationFactory()
        learner = _learner_in(organisation)

        response = _get_quick_view(
            educator_client(organisation), organisation, f"learners/{learner.pk}"
        )

        tree = html.fromstring(f"<div>{response.content.decode()}</div>")
        root = tree.xpath("//*[@x-data='messageBox']")[0]
        assert root.get("data-open-url-template").endswith("/messages/{pk}")
        assert not [
            a.get("href")
            for a in tree.xpath("//a[normalize-space()='Open conversation']")
            if a.get("href")
        ]

    def test_leaves_refresh_events_unchanged(self):
        assert LearnerQuickView.refresh_events == (LEARNER_CHANGED,)


@pytest.mark.django_db
class TestLearnerQuickViewMessageBoxHidden:
    @pytest.mark.usefixtures("messaging_closed")
    def test_shows_no_box_when_the_policy_refuses(self, educator_client):
        organisation = OrganisationFactory()
        learner = _learner_in(organisation)
        client, _ = _educator_with_conversation(
            educator_client, organisation, learner, ["hello"]
        )

        response = _get_quick_view(client, organisation, f"learners/{learner.pk}")

        content = response.content.decode()
        assert "quick-view-message-box" not in content
        assert "Open conversation" not in content

    @pytest.mark.usefixtures("messaging_closed")
    def test_shows_no_box_when_a_first_message_is_refused(self, educator_client):
        organisation = OrganisationFactory()
        learner = _learner_in(organisation)

        response = _get_quick_view(
            educator_client(organisation), organisation, f"learners/{learner.pk}"
        )

        assert "quick-view-message-box" not in response.content.decode()

    def test_shows_no_box_and_runs_no_messaging_query_when_messaging_is_off(
        self, educator_client, settings
    ):
        settings.MESSAGING_ENABLED = False
        organisation = OrganisationFactory()
        learner = _learner_in(organisation)
        client = educator_client(organisation)

        with CaptureQueriesContext(connection) as queries:
            response = _get_quick_view(client, organisation, f"learners/{learner.pk}")

        assert response.status_code == 200
        assert "quick-view-message-box" not in response.content.decode()
        assert not [q["sql"] for q in queries if "comms_" in q["sql"]]
