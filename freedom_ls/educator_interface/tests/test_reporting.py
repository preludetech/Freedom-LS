"""Tests for the on-screen reporting: badges, the Report tab, attention cards and learner courses."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast
from uuid import uuid4

import lxml.html
import pytest
import time_machine

from django.core.cache import cache
from django.core.files.base import ContentFile
from django.http import HttpResponse
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    TopicFactory,
)
from freedom_ls.educator_interface.reporting import (
    PROGRESS_STATUS_TONES,
    flag_badge,
    progress_status_badge,
)
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import Cohort, CohortMembership
from freedom_ls.learner_progress.tests.helpers import course_progress_record
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.reports.factories import GeneratedReportFactory
from freedom_ls.reports.gather import gather_cohort_report_data
from freedom_ls.reports.models import GeneratedReport
from freedom_ls.reports.report_data import (
    MIN_RESPONDENTS_FOR_PERCENTAGE,
    AtRiskFlag,
    ConfusionBlock,
    QuizColumn,
    QuizConfusion,
    SummaryTable,
)
from freedom_ls.reports.screen_cache import _cache_key
from freedom_ls.reports.statuses import ProgressStatus
from freedom_ls.reports.tests.helpers import (
    form_progress,
    quiz_form,
    topic_progress,
)
from freedom_ls.reports.tests.report_data_builders import (
    cohort_report_data,
    course_section,
)
from freedom_ls.reports.tests.test_views import (
    _role_config_granting_view_cohort_only,
)
from freedom_ls.role_based_permissions.utils import assign_object_role


@pytest.fixture(autouse=True)
def _site_context(mock_site_context):
    """Every test here builds site-aware objects and assigns roles."""


def _downloads_url(organisation_slug: str, cohort_pk: object) -> str:
    return reverse(
        "educator_interface:interface",
        kwargs={
            "organisation_slug": organisation_slug,
            "path_string": f"cohorts/{cohort_pk}/__tabs/report/__panels/downloads",
        },
    )


def _pdf_url(organisation_slug: str, cohort_pk: object, report_pk: object) -> str:
    return reverse(
        "educator_interface:cohort_report_download",
        kwargs={
            "organisation_slug": organisation_slug,
            "cohort_pk": cohort_pk,
            "report_pk": report_pk,
        },
    )


def _region_id(client: Client, url: str) -> str:
    """The id of the downloads region, read from the panel's own page."""
    document = lxml.html.fromstring(client.get(url).content.decode())
    return str(
        document.cssselect("[data-panel='downloads'] div[id^='panel-']")[0].get("id")
    )


def _refresh(client: Client, url: str) -> lxml.html.HtmlElement:
    """The downloads region as an htmx refresh of it returns it."""
    response = client.get(
        url, HTTP_HX_REQUEST="true", HTTP_HX_TARGET=_region_id(client, url)
    )
    assert response.status_code == 200
    return lxml.html.fromstring(response.content.decode())


def _generate(client: Client, url: str) -> HttpResponse:
    return cast(
        HttpResponse,
        client.post(
            f"{url}/__actions/generate_report",
            HTTP_HX_REQUEST="true",
            HTTP_HX_TARGET=_region_id(client, url),
        ),
    )


def _org_admin(organisation) -> object:
    admin = UserFactory(staff=True)
    assign_object_role(admin, organisation, "organisation_admin")
    return admin


def _course_with_topic():
    course = CourseFactory()
    ContentCollectionItemFactory(
        collection_object=course, child_object=TopicFactory(), order=0
    )
    return course


def _ready_report(cohort, **fields) -> GeneratedReport:
    report = cast(
        GeneratedReport,
        GeneratedReportFactory(
            cohort=cohort, status=GeneratedReport.STATUS_READY, **fields
        ),
    )
    report.file.save("r.pdf", ContentFile(b"%PDF-1.4 bytes"), save=True)
    return report


@pytest.mark.django_db
class TestReportTab:
    def test_the_report_tab_sits_between_courses_and_settings(self, logged_in_client):
        cohort = CohortFactory()
        client = logged_in_client(_org_admin(cohort.organisation))

        response = client.get(
            reverse(
                "educator_interface:interface",
                kwargs={
                    "organisation_slug": cohort.organisation.slug,
                    "path_string": f"cohorts/{cohort.pk}",
                },
            )
        )

        document = lxml.html.fromstring(response.content.decode())
        (nav,) = document.cssselect("nav[aria-label='Cohort sections']")
        assert [a.get("href").rsplit("/", 1)[-1] for a in nav.cssselect("a")] == [
            "overview",
            "learners",
            "courses",
            "report",
            "settings",
        ]

    def test_a_viewer_without_the_download_capability_gets_the_body_and_no_downloads_panel(
        self, logged_in_client, mock_site_context
    ):
        cohort = CohortFactory()
        viewer = UserFactory(staff=True)
        with _role_config_granting_view_cohort_only(mock_site_context.name):
            assign_object_role(viewer, cohort, "cohort_viewer")
            client = logged_in_client(viewer)
            tab = client.get(
                reverse(
                    "educator_interface:interface",
                    kwargs={
                        "organisation_slug": cohort.organisation.slug,
                        "path_string": f"cohorts/{cohort.pk}/__tabs/report",
                    },
                )
            )
            downloads = client.get(_downloads_url(cohort.organisation.slug, cohort.pk))

        document = lxml.html.fromstring(tab.content.decode())
        assert document.cssselect("[data-panel='body']")
        assert not document.cssselect("[data-panel='downloads']")
        assert downloads.status_code == 404

    def test_the_generate_button_disables_itself_and_shows_a_loading_label_while_posting(
        self, logged_in_client
    ):
        cohort = CohortFactory()
        client = logged_in_client(_org_admin(cohort.organisation))

        region = _refresh(client, _downloads_url(cohort.organisation.slug, cohort.pk))

        (form,) = region.cssselect("form[hx-post]")
        (button,) = form.cssselect("button[type='submit']")
        assert form.get("hx-disabled-elt") == "find button[type='submit']"
        labels = [" ".join(span.text_content().split()) for span in button]
        assert labels == ["Generate PDF report", "Generating…"]
        assert "[.htmx-request_&]:hidden" in button[0].get("class")
        assert "hidden" in button[1].get("class").split()

    def test_posting_the_action_creates_a_report_and_returns_the_in_flight_region(
        self, logged_in_client
    ):
        cohort = CohortFactory()
        client = logged_in_client(_org_admin(cohort.organisation))
        url = _downloads_url(cohort.organisation.slug, cohort.pk)

        response = _generate(client, url)

        region = lxml.html.fromstring(response.content.decode())
        assert response.status_code == 200
        assert GeneratedReport.objects.filter(cohort=cohort).count() == 1
        assert "A report is being generated" in region.text_content()

    def test_posting_again_while_one_is_in_flight_returns_the_same_region_without_a_second_report(
        self, logged_in_client
    ):
        cohort = CohortFactory()
        client = logged_in_client(_org_admin(cohort.organisation))
        url = _downloads_url(cohort.organisation.slug, cohort.pk)
        _generate(client, url)

        response = _generate(client, url)

        assert response.status_code == 200
        assert "A report is being generated" in response.content.decode()
        assert GeneratedReport.objects.filter(cohort=cohort).count() == 1

    def test_an_in_flight_region_polls_every_three_seconds(self, logged_in_client):
        cohort = CohortFactory()
        GeneratedReportFactory(cohort=cohort, status=GeneratedReport.STATUS_RUNNING)

        region = _refresh(
            logged_in_client(_org_admin(cohort.organisation)),
            _downloads_url(cohort.organisation.slug, cohort.pk),
        )

        assert region.cssselect("[hx-trigger='every 3s']")

    def test_an_in_flight_region_older_than_ten_minutes_stops_polling_and_offers_a_recheck(
        self, logged_in_client
    ):
        cohort = CohortFactory()
        report = GeneratedReportFactory(
            cohort=cohort, status=GeneratedReport.STATUS_PENDING
        )
        client = logged_in_client(_org_admin(cohort.organisation))
        url = _downloads_url(cohort.organisation.slug, cohort.pk)

        with time_machine.travel(report.requested_at + timedelta(minutes=11)):
            region = _refresh(client, url)

        assert not region.cssselect("[hx-trigger]")
        assert "This is taking longer than expected." in region.text_content()
        assert region.cssselect("a[hx-get]")

    def test_a_ready_region_links_to_the_download_and_does_not_poll(
        self, logged_in_client
    ):
        cohort = CohortFactory()
        report = _ready_report(cohort)

        region = _refresh(
            logged_in_client(_org_admin(cohort.organisation)),
            _downloads_url(cohort.organisation.slug, cohort.pk),
        )

        assert region.cssselect(
            f"a[href='{_pdf_url(cohort.organisation.slug, cohort.pk, report.pk)}']"
        )
        assert not region.cssselect("[hx-trigger]")

    def test_a_failed_region_shows_the_reason_and_offers_to_try_again(
        self, logged_in_client
    ):
        cohort = CohortFactory()
        GeneratedReportFactory(
            cohort=cohort,
            status=GeneratedReport.STATUS_FAILED,
            error_message="The cohort is too large to report on.",
        )

        region = _refresh(
            logged_in_client(_org_admin(cohort.organisation)),
            _downloads_url(cohort.organisation.slug, cohort.pk),
        )

        assert not region.cssselect("[hx-trigger]")
        assert "The cohort is too large to report on." in region.text_content()
        assert "Try again" in region.text_content()


@pytest.mark.django_db
class TestCohortReportDownload:
    def test_a_ready_report_downloads_as_a_private_attachment_named_for_the_cohort(
        self, logged_in_client
    ):
        organisation = OrganisationFactory(name="Acme School")
        cohort = CohortFactory(organisation=organisation, name="Year 9")
        report = _ready_report(cohort)

        response = logged_in_client(_org_admin(organisation)).get(
            _pdf_url(organisation.slug, cohort.pk, report.pk)
        )

        assert response.status_code == 200
        assert response["Cache-Control"] == "private, no-store, must-revalidate"
        assert (
            "acme-school-year-9-progress-report.pdf" in response["Content-Disposition"]
        )
        assert b"".join(response.streaming_content) == b"%PDF-1.4 bytes"

    def test_an_organisation_the_user_cannot_access_answers_404(self, logged_in_client):
        cohort = CohortFactory()
        report = _ready_report(cohort)
        outsider = _org_admin(OrganisationFactory())

        response = logged_in_client(outsider).get(
            _pdf_url(cohort.organisation.slug, cohort.pk, report.pk)
        )

        assert response.status_code == 404

    def test_a_cohort_outside_the_named_organisation_answers_404(
        self, logged_in_client
    ):
        organisation = OrganisationFactory()
        foreign = CohortFactory()
        report = _ready_report(foreign)

        response = logged_in_client(_org_admin(organisation)).get(
            _pdf_url(organisation.slug, foreign.pk, report.pk)
        )

        assert response.status_code == 404

    def test_another_cohorts_report_answers_404(self, logged_in_client):
        organisation = OrganisationFactory()
        cohort = CohortFactory(organisation=organisation)
        other = CohortFactory(organisation=organisation)
        report = _ready_report(other)

        response = logged_in_client(_org_admin(organisation)).get(
            _pdf_url(organisation.slug, cohort.pk, report.pk)
        )

        assert response.status_code == 404

    @pytest.mark.parametrize(
        "status", [GeneratedReport.STATUS_PENDING, GeneratedReport.STATUS_FAILED]
    )
    def test_a_report_that_is_not_ready_answers_404(self, logged_in_client, status):
        cohort = CohortFactory()
        report = GeneratedReportFactory(cohort=cohort, status=status)

        response = logged_in_client(_org_admin(cohort.organisation)).get(
            _pdf_url(cohort.organisation.slug, cohort.pk, report.pk)
        )

        assert response.status_code == 404

    def test_a_viewer_without_the_download_capability_answers_404(
        self, logged_in_client, mock_site_context
    ):
        cohort = CohortFactory()
        report = _ready_report(cohort)
        viewer = UserFactory(staff=True)
        with _role_config_granting_view_cohort_only(mock_site_context.name):
            assign_object_role(viewer, cohort, "cohort_viewer")

            response = logged_in_client(viewer).get(
                _pdf_url(cohort.organisation.slug, cohort.pk, report.pk)
            )

        assert response.status_code == 404


@pytest.mark.django_db
class TestProgressBadges:
    def test_the_three_statuses_map_to_muted_info_and_success(self) -> None:
        assert [PROGRESS_STATUS_TONES[status] for status in ProgressStatus] == [
            "muted",
            "info",
            "success",
        ]

    def test_a_completion_percentage_becomes_its_status_badge(self) -> None:
        badge = progress_status_badge(50)

        assert (badge.tone, badge.label) == ("info", "In progress")

    def test_a_flag_badge_is_toned_by_the_flags_severity(self) -> None:
        flag = AtRiskFlag(
            rule_id="inactive",
            label="No activity recently",
            reason="No activity recorded in over 7 days.",
            severity="warning",
        )

        badge = flag_badge(flag)

        assert (badge.tone, badge.label) == ("warning", "No activity recently")


def _attention_url(organisation_slug: str, cohort_pk: object) -> str:
    return reverse(
        "educator_interface:interface",
        kwargs={
            "organisation_slug": organisation_slug,
            "path_string": f"cohorts/{cohort_pk}/__tabs/overview/__panels/attention",
        },
    )


def _attention_region(
    client: Client, url: str, *, loaded: bool = True
) -> lxml.html.HtmlElement:
    """The attention region as the htmx fetch the skeleton makes returns it."""
    page = lxml.html.fromstring(client.get(url).content.decode())
    region_id = page.cssselect("[data-panel='attention'] div[id^='panel-']")[0].get(
        "id"
    )
    response = client.get(
        f"{url}?loaded=1" if loaded else url,
        HTTP_HX_REQUEST="true",
        HTTP_HX_TARGET=region_id,
    )
    assert response.status_code == 200
    return lxml.html.fromstring(response.content.decode())


@pytest.mark.django_db
class TestNeedsAttentionCard:
    def test_the_first_render_is_a_busy_skeleton_with_a_load_trigger(
        self, logged_in_client
    ):
        cohort = CohortFactory()
        client = logged_in_client(_org_admin(cohort.organisation))

        region = _attention_region(
            client,
            _attention_url(cohort.organisation.slug, cohort.pk),
            loaded=False,
        )

        assert region.get("aria-busy") == "true"
        assert len(region.cssselect("[hx-trigger='load']")) == 1

    def test_the_loaded_region_lists_a_flagged_learner_with_badges_reason_and_link(
        self, logged_in_client
    ):
        cohort = CohortFactory()
        CohortCourseRegistrationFactory(cohort=cohort, course=_course_with_topic())
        membership = CohortMembershipFactory(
            cohort=cohort,
            learner__user=UserFactory(first_name="Cy", last_name="Cook"),
        )
        client = logged_in_client(_org_admin(cohort.organisation))

        region = _attention_region(
            client, _attention_url(cohort.organisation.slug, cohort.pk)
        )

        (row,) = region.cssselect("li")
        assert [a.text_content() for a in row.cssselect("a")] == ["Cy Cook"]
        assert (
            row.cssselect("a")[0]
            .get("href")
            .endswith(f"/learners/{membership.learner_id}")
        )
        text = " ".join(row.text_content().split())
        assert "Not started" in text
        assert "No recorded activity" in text
        assert "Has not started any course item." in text
        assert region.get("aria-busy") is None

    def test_a_cohort_with_nobody_flagged_says_so(self, logged_in_client):
        cohort = CohortFactory()
        client = logged_in_client(_org_admin(cohort.organisation))

        region = _attention_region(
            client, _attention_url(cohort.organisation.slug, cohort.pk)
        )

        assert "Nobody needs attention right now" in region.text_content()

    def test_members_of_a_cohort_registered_for_no_course_are_not_flagged(
        self, logged_in_client
    ):
        cohort = CohortFactory()
        CohortMembershipFactory(cohort=cohort, learner__user=UserFactory())
        client = logged_in_client(_org_admin(cohort.organisation))

        region = _attention_region(
            client, _attention_url(cohort.organisation.slug, cohort.pk)
        )

        assert region.cssselect("li") == []
        assert "Nobody needs attention right now" in region.text_content()

    def test_a_removed_learner_is_not_listed(self, logged_in_client):
        cohort = CohortFactory()
        CohortMembershipFactory(
            cohort=cohort,
            learner=LearnerFactory(organisation=cohort.organisation, is_active=False),
        )
        client = logged_in_client(_org_admin(cohort.organisation))

        region = _attention_region(
            client, _attention_url(cohort.organisation.slug, cohort.pk)
        )

        assert region.cssselect("li") == []

    @override_settings(REPORTS_MAX_LEARNERS=1)
    def test_a_cohort_over_the_limit_shows_the_error_message(self, logged_in_client):
        cohort = CohortFactory()
        CohortMembershipFactory(cohort=cohort, learner__user=UserFactory())
        CohortMembershipFactory(cohort=cohort, learner__user=UserFactory())
        client = logged_in_client(_org_admin(cohort.organisation))

        region = _attention_region(
            client, _attention_url(cohort.organisation.slug, cohort.pk)
        )

        assert "exceeding the configured limit of 1" in region.text_content()


def _body_url(organisation_slug: str, cohort_pk: object) -> str:
    return reverse(
        "educator_interface:interface",
        kwargs={
            "organisation_slug": organisation_slug,
            "path_string": f"cohorts/{cohort_pk}/__tabs/report/__panels/body",
        },
    )


def _body_region(
    client: Client, url: str, *, query: str = "loaded=1"
) -> lxml.html.HtmlElement:
    """The report body region as the htmx fetch the skeleton makes returns it."""
    page = lxml.html.fromstring(client.get(url).content.decode())
    region_id = page.cssselect("[data-panel='body'] div[id^='panel-']")[0].get("id")
    response = client.get(
        f"{url}?{query}", HTTP_HX_REQUEST="true", HTTP_HX_TARGET=region_id
    )
    assert response.status_code == 200
    return lxml.html.fromstring(response.content.decode())


def _seeded_report_cohort() -> Cohort:
    """Two members: Ada finished the only topic, Bo has not started."""
    course = CourseFactory()
    topic = TopicFactory()
    ContentCollectionItemFactory(collection_object=course, child_object=topic, order=0)
    cohort: Cohort = CohortFactory()
    CohortCourseRegistrationFactory(cohort=cohort, course=course)
    for first_name, last_name in (("Ada", "Able"), ("Bo", "Baker")):
        user = UserFactory(first_name=first_name, last_name=last_name)
        CohortMembershipFactory(cohort=cohort, learner__user=user)
        record = course_progress_record(course, user)
        if first_name == "Ada":
            topic_progress(record, topic, complete_time=timezone.now())
    return cohort


def _at_a_glance(region: lxml.html.HtmlElement) -> dict[str, str]:
    return {
        dl.cssselect("dt")[0].text_content().strip(): dl.cssselect("dd")[0]
        .text_content()
        .strip()
        for dl in region.cssselect("dl")
    }


def _seed_report_cache(cohort: Cohort, quiz_confusion: QuizConfusion) -> None:
    quiz = QuizColumn(
        form_id=uuid4(), title="Orbit Quiz", abbreviation="OQ", pass_percentage=50
    )
    block = ConfusionBlock(questions=[quiz_confusion], shown=1, total=1)
    section = course_section(
        title="Astronomy",
        quizzes=[quiz],
        summary_tables=[SummaryTable(quizzes=[quiz], rows=[], continued=False)],
        confusions_by_quiz={quiz.form_id: block},
    )
    cache.set(
        _cache_key(cohort.site_id, cohort.pk, "report"),
        cohort_report_data(courses=[section]),
    )


def _confusion(**overrides: object) -> QuizConfusion:
    defaults: dict[str, object] = {
        "question_number": 1,
        "question_text": "What is an orbit?",
        "respondent_count": 12,
        "wrong_count": 8,
        "show_percentage": True,
        "wrong_percentage": 67,
        "distractors": [("A straight line", 5)],
        "correct_option_texts": ["A closed path around a body"],
    }
    defaults.update(overrides)
    return QuizConfusion(**defaults)


@pytest.mark.django_db
class TestCohortReportBody:
    @pytest.fixture(autouse=True)
    def _empty_cache(self):
        cache.clear()
        yield
        cache.clear()

    def test_the_first_render_is_a_busy_skeleton_with_a_load_trigger(
        self, logged_in_client
    ):
        cohort = CohortFactory()
        client = logged_in_client(_org_admin(cohort.organisation))

        region = _body_region(
            client, _body_url(cohort.organisation.slug, cohort.pk), query="x=1"
        )

        assert region.get("aria-busy") == "true"
        assert len(region.cssselect("[hx-trigger='load']")) == 1

    @time_machine.travel(datetime(2026, 3, 15, 10, 30, tzinfo=UTC), tick=False)
    def test_the_at_a_glance_figures_equal_the_gather_and_the_seeded_literals(
        self, logged_in_client
    ):
        cohort = _seeded_report_cohort()
        client = logged_in_client(_org_admin(cohort.organisation))

        region = _body_region(client, _body_url(cohort.organisation.slug, cohort.pk))

        gathered = gather_cohort_report_data(str(cohort.pk), cohort.site_id)
        assert _at_a_glance(region) == {
            "Learners in cohort": str(gathered.cohort_size),
            "Median completion": f"{gathered.median_completion}%",
            "Not started": str(gathered.not_started_count),
            "Completed everything": str(gathered.complete_count),
        }
        assert _at_a_glance(region) == {
            "Learners in cohort": "2",
            "Median completion": "50%",
            "Not started": "1",
            "Completed everything": "1",
        }
        assert "Figures as of 15 Mar 2026, 10:30" in region.text_content()

    def test_a_learner_name_in_a_summary_row_links_to_the_learner_page(
        self, logged_in_client
    ):
        cohort = _seeded_report_cohort()
        membership = CohortMembership.objects.get(
            cohort=cohort, learner__user__first_name="Ada"
        )
        client = logged_in_client(_org_admin(cohort.organisation))

        region = _body_region(client, _body_url(cohort.organisation.slug, cohort.pk))

        (link,) = region.cssselect("tbody a")[:1]
        assert link.text_content() == "Ada Able"
        assert link.get("href").endswith(f"/learners/{membership.learner_id}")

    def test_the_summary_rows_carry_status_completion_and_the_items_count(
        self, logged_in_client
    ):
        cohort = _seeded_report_cohort()
        client = logged_in_client(_org_admin(cohort.organisation))

        region = _body_region(client, _body_url(cohort.organisation.slug, cohort.pk))

        first_row = " ".join(region.cssselect("tbody tr")[0].text_content().split())
        assert "Ada Able" in first_row
        assert "Complete" in first_row
        assert "1 of 1 items" in first_row

    def test_refresh_replaces_a_stale_cache_entry_with_fresh_figures(
        self, logged_in_client
    ):
        cohort = _seeded_report_cohort()
        client = logged_in_client(_org_admin(cohort.organisation))
        url = _body_url(cohort.organisation.slug, cohort.pk)
        cache.set(
            _cache_key(cohort.site_id, cohort.pk, "report"),
            cohort_report_data(cohort_size=0, median_completion=99),
        )

        stale = _body_region(client, url)
        fresh = _body_region(client, url, query="loaded=1&refresh=1")

        assert _at_a_glance(stale)["Median completion"] == "99%"
        assert _at_a_glance(fresh)["Median completion"] == "50%"

    def test_the_refresh_control_asks_for_a_regather_into_the_same_region(
        self, logged_in_client
    ):
        cohort = _seeded_report_cohort()
        client = logged_in_client(_org_admin(cohort.organisation))

        region = _body_region(client, _body_url(cohort.organisation.slug, cohort.pk))

        (button,) = region.cssselect("button[hx-get]")
        assert button.get("hx-get").endswith("?loaded=1&refresh=1")
        assert button.get("hx-target") == f"#{region.get('id')}"
        assert button.get("hx-swap") == "outerHTML"

    def test_a_quiz_with_enough_respondents_shows_a_percentage(self, logged_in_client):
        cohort = CohortFactory()
        client = logged_in_client(_org_admin(cohort.organisation))
        _seed_report_cache(cohort, _confusion())

        region = _body_region(client, _body_url(cohort.organisation.slug, cohort.pk))

        text = " ".join(region.text_content().split())
        assert "67% of 12 learners" in text
        assert "A straight line \u00d75" in text
        assert "A closed path around a body" in text

    def test_a_quiz_with_few_respondents_shows_counts_not_a_percentage(
        self, logged_in_client
    ):
        cohort = CohortFactory()
        client = logged_in_client(_org_admin(cohort.organisation))
        _seed_report_cache(
            cohort,
            _confusion(
                respondent_count=MIN_RESPONDENTS_FOR_PERCENTAGE - 1,
                wrong_count=3,
                show_percentage=False,
                wrong_percentage=None,
            ),
        )

        region = _body_region(client, _body_url(cohort.organisation.slug, cohort.pk))

        text = " ".join(region.text_content().split())
        assert "3 of 9 learners" in text
        assert "%" not in text.split("Got it wrong")[-1]

    def test_a_cohort_without_incorrect_answers_says_so(self, logged_in_client):
        cohort = _seeded_report_cohort()
        client = logged_in_client(_org_admin(cohort.organisation))

        region = _body_region(client, _body_url(cohort.organisation.slug, cohort.pk))

        assert (
            "No quiz in this report has any incorrect answers to analyse."
            in region.text_content()
        )

    @override_settings(REPORTS_MAX_LEARNERS=1)
    def test_a_cohort_over_the_limit_shows_the_message_and_no_tables(
        self, logged_in_client
    ):
        cohort = _seeded_report_cohort()
        client = logged_in_client(_org_admin(cohort.organisation))

        region = _body_region(client, _body_url(cohort.organisation.slug, cohort.pk))

        assert "exceeding the configured limit of 1" in region.text_content()
        assert region.cssselect("table") == []

    def test_the_body_never_shows_wrong_answer_text(self, logged_in_client):
        cohort = _seeded_report_cohort()
        client = logged_in_client(_org_admin(cohort.organisation))

        region = _body_region(client, _body_url(cohort.organisation.slug, cohort.pk))

        assert "Wrong answers" not in region.text_content()


def _courses_panel(client: Client, organisation_slug: str, learner: object) -> str:
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
    return " ".join(
        lxml.html.fromstring(response.content.decode()).text_content().split()
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


_NEW_REPORTING_FILES = [
    "reporting.py",
    "templates/educator_interface/panels/dashboard.html",
    "templates/educator_interface/panels/dashboard_region.html",
    "templates/educator_interface/panels/lazy_panel.html",
    "templates/educator_interface/panels/_lazy_region.html",
    "templates/educator_interface/panels/cohort_needs_attention_region.html",
    "templates/educator_interface/panels/cohort_report_downloads.html",
    "templates/educator_interface/panels/cohort_report_downloads_region.html",
    "templates/educator_interface/panels/cohort_report_body_region.html",
    "templates/educator_interface/panels/learner_courses.html",
    "templates/educator_interface/partials/learner_badges.html",
]


@pytest.mark.django_db
@pytest.mark.parametrize("relative_path", _NEW_REPORTING_FILES)
def test_reporting_surfaces_never_read_the_stored_progress_percentage(
    relative_path: str,
) -> None:
    """Figures are recomputed from progress rows, never read from the stored column."""
    source = (Path(__file__).parent.parent / relative_path).read_text()

    assert "progress_percentage" not in source
