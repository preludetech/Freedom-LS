"""Tests for freedom_ls.reports.tasks.generate_cohort_report."""

from __future__ import annotations

import pytest

from django.template.loader import render_to_string
from django.test import override_settings
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
)
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
    QuestionAnswerFactory,
    QuestionOptionFactory,
)
from freedom_ls.form_engine.models import FormStrategy, QuestionType
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
)
from freedom_ls.learner_progress.tests.helpers import course_progress_record
from freedom_ls.reports.factories import GeneratedReportFactory
from freedom_ls.reports.models import GeneratedReport
from freedom_ls.reports.render import ReportRenderError
from freedom_ls.reports.report_data import CohortReportData
from freedom_ls.reports.tasks import generate_cohort_report
from freedom_ls.reports.tests.helpers import form_progress
from freedom_ls.tests.factories import SiteFactory

pytestmark = pytest.mark.django_db

FAKE_PDF_BYTES = b"%PDF-1.4 fake report bytes"


class TestGenerateCohortReportHappyPath:
    def test_successful_generation_leaves_status_ready(
        self, mock_site_context: object, mocker: object
    ) -> None:
        cohort = CohortFactory()
        report = GeneratedReportFactory(
            cohort=cohort, status=GeneratedReport.STATUS_PENDING
        )

        mocker.patch(
            "freedom_ls.reports.tasks.render_report_pdf", return_value=FAKE_PDF_BYTES
        )

        generate_cohort_report(str(report.pk), report.site_id)

        report.refresh_from_db()
        assert report.status == GeneratedReport.STATUS_READY

    def test_successful_generation_produces_non_empty_file(
        self, mock_site_context: object, mocker: object
    ) -> None:
        cohort = CohortFactory()
        report = GeneratedReportFactory(
            cohort=cohort, status=GeneratedReport.STATUS_PENDING
        )

        mocker.patch(
            "freedom_ls.reports.tasks.render_report_pdf", return_value=FAKE_PDF_BYTES
        )

        generate_cohort_report(str(report.pk), report.site_id)

        report.refresh_from_db()
        assert report.file.size > 0


def _cohort_with_a_missed_question() -> CohortFactory:
    """A cohort whose one learner answered the quiz's only question wrongly."""
    cohort = CohortFactory()
    course = CourseFactory()
    CohortCourseRegistrationFactory(cohort=cohort, course=course)
    quiz = FormFactory(strategy=FormStrategy.QUIZ, quiz_pass_percentage=50)
    ContentCollectionItemFactory(collection_object=course, child_object=quiz, order=0)
    question = FormQuestionFactory(
        form_page=FormPageFactory(form=quiz, order=0),
        question="Which body does the Earth orbit?",
        type=QuestionType.MULTIPLE_CHOICE,
        order=0,
    )
    QuestionOptionFactory(question=question, text="The Sun", correct=True, order=0)
    distractor = QuestionOptionFactory(
        question=question, text="The Moon", correct=False, order=1
    )
    learner = UserFactory()
    CohortMembershipFactory(cohort=cohort, learner__user=learner)
    attempt = form_progress(
        course_progress_record(course, learner),
        quiz,
        completed_time=timezone.now(),
        scores={"score": 0, "max_score": 1},
    )
    QuestionAnswerFactory(
        form_progress=attempt, question=question
    ).selected_options.add(distractor)
    return cohort


class TestGenerateCohortReportCarriesNoQuestionDetail:
    @pytest.mark.parametrize("requester_is_superuser", [True, False])
    def test_the_rendered_document_holds_no_question_or_option_text(
        self, mock_site_context: object, mocker: object, requester_is_superuser: bool
    ) -> None:
        cohort = _cohort_with_a_missed_question()
        requester = UserFactory(is_superuser=requester_is_superuser)
        report = GeneratedReportFactory(
            cohort=cohort,
            requested_by=requester,
            status=GeneratedReport.STATUS_PENDING,
        )
        documents: list[str] = []

        def capture(data: CohortReportData) -> bytes:
            documents.append(
                render_to_string(
                    "reports/report.html",
                    {"data": data, "theme_tokens": "", "print_css": ""},
                )
            )
            return FAKE_PDF_BYTES

        mocker.patch("freedom_ls.reports.tasks.render_report_pdf", side_effect=capture)

        generate_cohort_report(str(report.pk), report.site_id)

        assert len(documents) == 1
        assert "Which body does the Earth orbit?" not in documents[0]
        assert "The Sun" not in documents[0]
        assert "The Moon" not in documents[0]
        assert "Incorrect answers" not in documents[0]


class TestGenerateCohortReportRequester:
    def test_report_data_carries_the_requesters_display_name(
        self, mock_site_context: object, mocker: object
    ) -> None:
        cohort = CohortFactory()
        requester = UserFactory(first_name="Ada", last_name="Lovelace")
        report = GeneratedReportFactory(
            cohort=cohort,
            requested_by=requester,
            status=GeneratedReport.STATUS_PENDING,
        )

        render = mocker.patch(
            "freedom_ls.reports.tasks.render_report_pdf", return_value=FAKE_PDF_BYTES
        )

        generate_cohort_report(str(report.pk), report.site_id)

        data = render.call_args.args[0]
        assert data.requested_by_name == "Ada Lovelace"

    def test_report_without_a_requester_still_generates(
        self, mock_site_context: object, mocker: object
    ) -> None:
        cohort = CohortFactory()
        report = GeneratedReportFactory(
            cohort=cohort, requested_by=None, status=GeneratedReport.STATUS_PENDING
        )

        render = mocker.patch(
            "freedom_ls.reports.tasks.render_report_pdf", return_value=FAKE_PDF_BYTES
        )

        generate_cohort_report(str(report.pk), report.site_id)

        report.refresh_from_db()
        assert report.status == GeneratedReport.STATUS_READY
        assert render.call_args.args[0].requested_by_name == ""


class TestGenerateCohortReportRenderFailure:
    def test_render_error_leaves_status_failed(
        self, mock_site_context: object, mocker: object
    ) -> None:
        cohort = CohortFactory()
        report = GeneratedReportFactory(
            cohort=cohort, status=GeneratedReport.STATUS_PENDING
        )

        mocker.patch(
            "freedom_ls.reports.tasks.render_report_pdf",
            side_effect=ReportRenderError("boom"),
        )

        generate_cohort_report(str(report.pk), report.site_id)

        report.refresh_from_db()
        assert report.status == GeneratedReport.STATUS_FAILED

    def test_render_error_sets_readable_error_message(
        self, mock_site_context: object, mocker: object
    ) -> None:
        cohort = CohortFactory()
        report = GeneratedReportFactory(
            cohort=cohort, status=GeneratedReport.STATUS_PENDING
        )

        mocker.patch(
            "freedom_ls.reports.tasks.render_report_pdf",
            side_effect=ReportRenderError("could not resolve a static asset"),
        )

        generate_cohort_report(str(report.pk), report.site_id)

        report.refresh_from_db()
        assert report.error_message == "could not resolve a static asset"

    def test_render_error_sets_finished_at(
        self, mock_site_context: object, mocker: object
    ) -> None:
        cohort = CohortFactory()
        report = GeneratedReportFactory(
            cohort=cohort, status=GeneratedReport.STATUS_PENDING
        )

        mocker.patch(
            "freedom_ls.reports.tasks.render_report_pdf",
            side_effect=ReportRenderError("boom"),
        )

        generate_cohort_report(str(report.pk), report.site_id)

        report.refresh_from_db()
        assert report.finished_at is not None

    def test_render_error_leaves_cohort_immediately_regeneratable(
        self, mock_site_context: object, mocker: object
    ) -> None:
        """A failed report does not hold the partial unique index open."""
        cohort = CohortFactory()
        report = GeneratedReportFactory(
            cohort=cohort, status=GeneratedReport.STATUS_PENDING
        )

        mocker.patch(
            "freedom_ls.reports.tasks.render_report_pdf",
            side_effect=ReportRenderError("boom"),
        )

        generate_cohort_report(str(report.pk), report.site_id)

        second = GeneratedReportFactory(
            cohort=cohort, status=GeneratedReport.STATUS_PENDING
        )

        assert second.pk is not None


class TestGenerateCohortReportTooLarge:
    def test_cohort_over_max_learners_leaves_status_failed(
        self, mock_site_context: object
    ) -> None:
        cohort = CohortFactory()
        CohortMembershipFactory(cohort=cohort)
        CohortMembershipFactory(cohort=cohort)
        report = GeneratedReportFactory(
            cohort=cohort, status=GeneratedReport.STATUS_PENDING
        )

        with override_settings(REPORTS_MAX_LEARNERS=1):
            generate_cohort_report(str(report.pk), report.site_id)

        report.refresh_from_db()
        assert report.status == GeneratedReport.STATUS_FAILED

    def test_cohort_over_max_learners_error_message_names_the_limit(
        self, mock_site_context: object
    ) -> None:
        cohort = CohortFactory()
        CohortMembershipFactory(cohort=cohort)
        CohortMembershipFactory(cohort=cohort)
        report = GeneratedReportFactory(
            cohort=cohort, status=GeneratedReport.STATUS_PENDING
        )

        with override_settings(REPORTS_MAX_LEARNERS=1):
            generate_cohort_report(str(report.pk), report.site_id)

        report.refresh_from_db()
        assert "1" in report.error_message
        assert "REPORTS_MAX_LEARNERS" not in report.error_message


class TestGenerateCohortReportUnexpectedException:
    def test_unexpected_exception_type_leaves_status_failed(
        self, mock_site_context: object, mocker: object
    ) -> None:
        cohort = CohortFactory()
        report = GeneratedReportFactory(
            cohort=cohort, status=GeneratedReport.STATUS_PENDING
        )

        mocker.patch(
            "freedom_ls.reports.tasks.gather_cohort_report_data",
            side_effect=TypeError("boom"),
        )

        with pytest.raises(TypeError):
            generate_cohort_report(str(report.pk), report.site_id)

        report.refresh_from_db()
        assert report.status == GeneratedReport.STATUS_FAILED

    def test_unexpected_exception_still_propagates(
        self, mock_site_context: object, mocker: object
    ) -> None:
        """The worker's own error reporting must still see the exception."""
        cohort = CohortFactory()
        report = GeneratedReportFactory(
            cohort=cohort, status=GeneratedReport.STATUS_PENDING
        )

        mocker.patch(
            "freedom_ls.reports.tasks.gather_cohort_report_data",
            side_effect=TypeError("boom"),
        )

        with pytest.raises(TypeError, match="boom"):
            generate_cohort_report(str(report.pk), report.site_id)


class TestGenerateCohortReportSiteFiltering:
    def test_task_does_nothing_for_report_on_another_site(
        self, mock_site_context: object
    ) -> None:
        cohort = CohortFactory()
        report = GeneratedReportFactory(
            cohort=cohort, status=GeneratedReport.STATUS_PENDING
        )
        other_site = SiteFactory()

        generate_cohort_report(str(report.pk), other_site.pk)

        report.refresh_from_db()
        assert report.status == GeneratedReport.STATUS_PENDING
