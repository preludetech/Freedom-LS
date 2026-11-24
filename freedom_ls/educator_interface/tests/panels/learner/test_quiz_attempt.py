"""The attempt review page: educator_interface/panels/learner/quiz_attempt.py."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

import lxml.html
import pytest
from pytest_django.fixtures import DjangoAssertNumQueries

from django.db import connection
from django.http import HttpRequest
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.educator_interface.panels.common.request import (
    OrganisationScopedRequest,
)
from freedom_ls.educator_interface.panels.learner.quiz_attempt import (
    openable_sitting_ids,
)
from freedom_ls.educator_interface.tests.helpers import (
    _get_document,
    _get_quick_view,
    _header_of,
    _interface_url,
    organisation_admin_viewer,
)
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
    QuestionAnswerFactory,
    QuestionOptionFactory,
    served_paper_of,
)
from freedom_ls.form_engine.models import (
    Form,
    FormContent,
    FormPage,
    FormProgress,
    FormQuestion,
    FormStrategy,
    QuestionAnswer,
    QuestionOption,
)
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import Learner
from freedom_ls.learner_progress.factories import (
    CourseFormAttemptFactory,
    CourseProgressFactory,
)
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.role_based_permissions.utils import assign_object_role

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("mock_site_context")]


def _sitting(
    learner: Learner,
    *,
    strategy: str = FormStrategy.QUIZ,
    completed: bool = True,
    pass_percentage: int | None = 50,
    scores: dict[str, int] | None = None,
    title: str = "Safety quiz",
    course_title: str = "Aviation basics",
    **attempt_kwargs: object,
) -> FormProgress:
    attempt = CourseFormAttemptFactory(
        form=FormFactory(
            title=title, strategy=strategy, quiz_pass_percentage=pass_percentage
        ),
        course_progress=CourseProgressFactory(
            learner=learner, course=CourseFactory(title=course_title)
        ),
        form_progress__completed_time=timezone.now() if completed else None,
        form_progress__scores=scores or {"score": 2, "max_score": 3},
        **attempt_kwargs,
    )
    return cast(FormProgress, attempt.form_progress)


def _page(
    client: Client, organisation: Organisation, sitting: FormProgress
) -> lxml.html.HtmlElement:
    return _get_document(
        client, _interface_url(organisation.slug, f"quiz-attempts/{sitting.pk}")
    )


def _admin_client(
    organisation: Organisation, logged_in_client: Callable[[User], Client]
) -> Client:
    return logged_in_client(organisation_admin_viewer(organisation))


def _text(element: lxml.html.HtmlElement) -> str:
    return " ".join(element.text_content().split())


def test_an_organisation_admin_sees_the_label_the_subtitle_and_the_summary_rows(
    logged_in_client,
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(
        organisation=organisation, user__first_name="Ada", user__last_name="Lovelace"
    )
    sitting = _sitting(learner)

    document = _page(
        _admin_client(organisation, logged_in_client), organisation, sitting
    )

    (heading,) = document.cssselect("#instance-title")
    assert _text(heading) == "Safety quiz, attempt 1"
    assert "Ada Lovelace · Aviation basics" in _text(_header_of(document))
    (panel,) = document.cssselect("section[data-panel='summary']")
    assert [_text(label) for label in panel.cssselect("dt")] == [
        "Started",
        "Completed",
        "Pass mark (current setting)",
    ]


def test_the_header_stats_read_the_stored_score_and_the_verdict(logged_in_client):
    organisation = OrganisationFactory()
    sitting = _sitting(
        LearnerFactory(organisation=organisation),
        pass_percentage=50,
        scores={"score": 2, "max_score": 3},
    )

    document = _page(
        _admin_client(organisation, logged_in_client), organisation, sitting
    )

    header = _text(_header_of(document))
    assert "Score 2/3" in header
    assert "Percentage 67%" in header
    assert "Result Passed" in header


def test_a_quiz_with_no_pass_mark_reads_no_pass_mark_in_the_header_and_the_summary(
    logged_in_client,
):
    organisation = OrganisationFactory()
    sitting = _sitting(LearnerFactory(organisation=organisation), pass_percentage=None)

    document = _page(
        _admin_client(organisation, logged_in_client), organisation, sitting
    )

    assert "Result No pass mark" in _text(_header_of(document))
    (panel,) = document.cssselect("section[data-panel='summary']")
    assert "Pass mark (current setting) No pass mark" in _text(panel)


def test_an_unreadable_score_reads_not_scored_in_the_header_not_no_pass_mark(
    logged_in_client: Callable[[User], Client],
) -> None:
    organisation = OrganisationFactory()
    sitting = _sitting(
        LearnerFactory(organisation=organisation),
        pass_percentage=60,
        scores={"score": 0, "max_score": 0},
    )

    document = _page(
        _admin_client(organisation, logged_in_client), organisation, sitting
    )

    header = _text(_header_of(document))
    assert "Result Not scored" in header
    assert "No pass mark" not in header


def test_the_quick_view_of_an_unreadable_score_reads_not_scored(
    logged_in_client: Callable[[User], Client],
) -> None:
    organisation = OrganisationFactory()
    sitting = _sitting(
        LearnerFactory(organisation=organisation),
        pass_percentage=60,
        scores={"score": 0, "max_score": 0},
    )

    response = _get_quick_view(
        _admin_client(organisation, logged_in_client),
        organisation,
        f"quiz-attempts/{sitting.pk}",
    )

    text = _text(lxml.html.fromstring(response.content.decode()))
    assert "Result Not scored" in text
    assert "No pass mark" not in text


def test_the_back_link_returns_to_the_learners_courses_tab(logged_in_client):
    organisation = OrganisationFactory()
    learner = LearnerFactory(
        organisation=organisation, user__first_name="Ada", user__last_name="Lovelace"
    )
    sitting = _sitting(learner)

    document = _page(
        _admin_client(organisation, logged_in_client), organisation, sitting
    )

    (link,) = document.cssselect("#breadcrumbs a")
    assert _text(link) == "Back to Ada Lovelace"
    assert link.get("href") == _interface_url(
        organisation.slug, f"learners/{learner.pk}/__tabs/courses"
    )


def test_a_course_another_organisation_owns_names_its_owner_in_the_subtitle(
    logged_in_client,
):
    organisation = OrganisationFactory()
    owner = OrganisationFactory(name="Acme Training")
    learner = LearnerFactory(
        organisation=organisation, user__first_name="Ada", user__last_name="Lovelace"
    )
    sitting = _sitting(learner)
    course = sitting.course_attempt.course_progress.course
    course.organisations.add(owner)

    document = _page(
        _admin_client(organisation, logged_in_client), organisation, sitting
    )

    assert "Ada Lovelace · Aviation basics · Shared by Acme Training" in _text(
        _header_of(document)
    )


def _outside_cohort(organisation: Organisation) -> tuple[User, FormProgress]:
    """A cohort educator, and a learner who is in no cohort they hold."""
    educator = cast(User, UserFactory(staff=True))
    assign_object_role(
        educator, CohortFactory(organisation=organisation), "cohort_admin"
    )
    return educator, _sitting(LearnerFactory(organisation=organisation))


def _through_hidden_cohort(organisation: Organisation) -> tuple[User, FormProgress]:
    """A cohort educator, and a visible learner whose course came through a
    cohort the educator cannot see."""
    visible = CohortFactory(organisation=organisation)
    hidden = CohortFactory(organisation=organisation)
    educator = cast(User, UserFactory(staff=True))
    assign_object_role(educator, visible, "cohort_admin")
    learner = LearnerFactory(organisation=organisation)
    CohortMembershipFactory(cohort=visible, learner=learner)
    CohortMembershipFactory(cohort=hidden, learner=learner)
    course = CourseFactory(title="Aviation basics")
    registration = CohortCourseRegistrationFactory(cohort=hidden, course=course)
    attempt = CourseFormAttemptFactory(
        form=FormFactory(strategy=FormStrategy.QUIZ),
        course_progress=CourseProgressFactory(
            learner=learner,
            course=course,
            learner_registration=None,
            cohort_registration=registration,
        ),
        form_progress__completed_time=timezone.now(),
        form_progress__scores={"score": 2, "max_score": 3},
    )
    return educator, cast(FormProgress, attempt.form_progress)


def _other_organisations_educator(
    organisation: Organisation,
) -> tuple[User, FormProgress]:
    return (
        organisation_admin_viewer(OrganisationFactory()),
        _sitting(LearnerFactory(organisation=organisation)),
    )


def _without_view_learner(organisation: Organisation) -> tuple[User, FormProgress]:
    educator = cast(User, UserFactory(staff=True))
    assign_object_role(educator, organisation, "organisation_staff_viewer")
    return educator, _sitting(LearnerFactory(organisation=organisation))


def _not_a_quiz(organisation: Organisation) -> tuple[User, FormProgress]:
    return organisation_admin_viewer(organisation), _sitting(
        LearnerFactory(organisation=organisation),
        strategy=FormStrategy.CATEGORY_VALUE_SUM,
    )


def _in_progress(organisation: Organisation) -> tuple[User, FormProgress]:
    return organisation_admin_viewer(organisation), _sitting(
        LearnerFactory(organisation=organisation), completed=False
    )


def _without_a_course_attempt(organisation: Organisation) -> tuple[User, FormProgress]:
    learner = LearnerFactory(organisation=organisation)
    sitting = _sitting(learner)
    sitting.course_attempt.delete()
    return organisation_admin_viewer(organisation), FormProgress.objects.get(
        pk=sitting.pk
    )


def _sat_by_someone_else(organisation: Organisation) -> tuple[User, FormProgress]:
    sitting = _sitting(LearnerFactory(organisation=organisation))
    sitting.user = UserFactory()
    sitting.save()
    return organisation_admin_viewer(organisation), sitting


@pytest.mark.parametrize(
    "build",
    [
        _outside_cohort,
        _through_hidden_cohort,
        _other_organisations_educator,
        _without_view_learner,
        _not_a_quiz,
        _in_progress,
        _without_a_course_attempt,
        _sat_by_someone_else,
    ],
)
@pytest.mark.parametrize("suffix", ["", "/__quick-view"])
def test_a_sitting_the_educator_may_not_open_is_a_404(build, suffix, logged_in_client):
    organisation = OrganisationFactory()
    educator, sitting = build(organisation)

    response = logged_in_client(educator).get(
        _interface_url(organisation.slug, f"quiz-attempts/{sitting.pk}{suffix}"),
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 404


def test_the_bare_section_path_is_a_404(logged_in_client):
    organisation = OrganisationFactory()

    response = _admin_client(organisation, logged_in_client).get(
        _interface_url(organisation.slug, "quiz-attempts")
    )

    assert response.status_code == 404


def _scoped_request(organisation: Organisation, viewer: User) -> HttpRequest:
    request = HttpRequest()
    request.user = viewer
    cast(OrganisationScopedRequest, request).organisation = organisation
    return request


def test_openable_sitting_ids_costs_no_more_queries_for_twenty_sittings_than_for_two(
    django_assert_max_num_queries: DjangoAssertNumQueries,
):
    organisation = OrganisationFactory()
    viewer = organisation_admin_viewer(organisation)
    learner = LearnerFactory(organisation=organisation)
    course_progress = CourseProgressFactory(learner=learner)
    form = FormFactory(strategy=FormStrategy.QUIZ)

    def sit(count: int) -> list[FormProgress]:
        return [
            CourseFormAttemptFactory(
                form=form,
                course_progress=course_progress,
                form_progress__completed_time=timezone.now(),
            ).form_progress
            for _ in range(count)
        ]

    two = sit(2)
    with django_assert_max_num_queries(12) as bound:
        openable_sitting_ids(
            cast(OrganisationScopedRequest, _scoped_request(organisation, viewer)),
            [s.pk for s in two],
        )
    twenty = two + sit(18)

    with django_assert_max_num_queries(len(bound.captured_queries)):
        opened = openable_sitting_ids(
            cast(OrganisationScopedRequest, _scoped_request(organisation, viewer)),
            [s.pk for s in twenty],
        )

    assert len(opened) == 20


def test_the_page_stays_under_its_query_bound(
    logged_in_client, django_assert_max_num_queries: DjangoAssertNumQueries
):
    organisation = OrganisationFactory()
    sitting = _sitting(LearnerFactory(organisation=organisation))
    client = _admin_client(organisation, logged_in_client)
    url = _interface_url(organisation.slug, f"quiz-attempts/{sitting.pk}")

    with django_assert_max_num_queries(60):
        response = client.get(url)

    assert response.status_code == 200


def _form_page(**kwargs: object) -> FormPage:
    return cast(FormPage, FormPageFactory(**kwargs))


def _paper_sitting(
    organisation: Organisation, form: Form, **progress_kwargs: object
) -> FormProgress:
    attempt = CourseFormAttemptFactory(
        form=form,
        course_progress=CourseProgressFactory(
            learner=LearnerFactory(organisation=organisation)
        ),
        form_progress__completed_time=timezone.now(),
        **{
            f"form_progress__{key}": value
            for key, value in {
                "scores": {"score": 0, "max_score": 0},
                **progress_kwargs,
            }.items()
        },
    )
    return cast(FormProgress, attempt.form_progress)


def _question(
    page: FormPage, text: str, order: int, options: list[tuple[str, bool]]
) -> tuple[FormQuestion, list[QuestionOption]]:
    question = cast(
        FormQuestion,
        FormQuestionFactory(
            form_page=page, question=text, order=order, type="multiple_choice"
        ),
    )
    return question, [
        cast(
            QuestionOption,
            QuestionOptionFactory(
                question=question, text=name, correct=correct, order=i
            ),
        )
        for i, (name, correct) in enumerate(options)
    ]


def _answer(
    sitting: FormProgress, question: FormQuestion, *chosen: QuestionOption
) -> QuestionAnswer:
    answer = cast(
        QuestionAnswer,
        QuestionAnswerFactory(form_progress=sitting, question=question),
    )
    answer.selected_options.add(*chosen)
    return answer


def _quiz() -> Form:
    return cast(Form, FormFactory(strategy=FormStrategy.QUIZ, quiz_pass_percentage=50))


def _paper_text(
    client: Client, organisation: Organisation, sitting: FormProgress
) -> str:
    return _text(
        _page(client, organisation, sitting).cssselect("section[data-panel='paper']")[0]
    )


def test_the_paper_follows_the_served_order_and_leaves_out_what_was_not_served(
    logged_in_client,
):
    organisation = OrganisationFactory()
    form = _quiz()
    first = _form_page(form=form, title="Alpha page", order=1)
    second = _form_page(form=form, title="Beta page", order=2)
    q_a, (a_1, a_2) = _question(
        first, "Question A", 1, [("A one", True), ("A two", False)]
    )
    q_b, _ = _question(first, "Question B", 2, [("B one", True), ("B two", False)])
    q_c, (c_1,) = _question(second, "Question C", 1, [("C one", True)])
    sitting = _paper_sitting(
        organisation,
        form,
        served_paper=served_paper_of(
            [(second, [q_c]), (first, [q_a])],
            {q_c: [c_1], q_a: [a_2, a_1]},
        ),
    )
    _answer(sitting, q_a, a_1)

    text = _paper_text(
        _admin_client(organisation, logged_in_client), organisation, sitting
    )

    assert text.index("Page 1 of 2: Beta page") < text.index("Question C")
    assert text.index("Question C") < text.index("Page 2 of 2: Alpha page")
    assert text.index("Page 2 of 2: Alpha page") < text.index("Question A")
    assert text.index("A two") < text.index("A one")
    assert "Question B" not in text
    assert str(q_b.id) not in text
    assert str(q_a.id) in text
    assert "predates" not in text


@pytest.mark.parametrize(
    ("asked_only", "left_out_shown"),
    [(True, False), (False, True)],
    ids=["asked-only", "neither"],
)
def test_a_sitting_without_a_served_paper_says_it_predates_the_record(
    logged_in_client, asked_only, left_out_shown
):
    organisation = OrganisationFactory()
    form = _quiz()
    page = _form_page(form=form, title="Only page", order=1)
    q_a, _ = _question(page, "Question A", 1, [("A one", True)])
    _question(page, "Question B", 2, [("B one", True)])
    sitting = _paper_sitting(
        organisation,
        form,
        asked={"pages": [str(page.id)], "questions": [str(q_a.id)], "content": []}
        if asked_only
        else None,
    )

    text = _paper_text(
        _admin_client(organisation, logged_in_client), organisation, sitting
    )

    assert "This attempt predates the record of the served order." in text
    assert "Question A" in text
    assert ("Question B" in text) is left_out_shown


def test_a_served_item_deleted_since_shows_the_missing_note_and_no_stale_score_note(
    logged_in_client,
):
    organisation = OrganisationFactory()
    form = _quiz()
    page = _form_page(form=form, title="Only page", order=1)
    q_a, (a_1,) = _question(page, "Question A", 1, [("A one", True)])
    q_b, (b_1,) = _question(page, "Question B", 2, [("B one", True)])
    sitting = _paper_sitting(
        organisation,
        form,
        served_paper=served_paper_of([(page, [q_a, q_b])], {q_a: [a_1], q_b: [b_1]}),
    )
    q_b.delete()

    text = _paper_text(
        _admin_client(organisation, logged_in_client), organisation, sitting
    )

    assert "have since been deleted from the quiz" in text
    assert "This quiz has changed" not in text


@pytest.mark.parametrize(
    ("chosen", "shown", "hidden", "learner_marks"),
    [
        ([0], "Marked correct", "Did not answer", 1),
        ([1], "Marked incorrect", "Did not answer", 1),
        ([], "Did not answer Marked incorrect", "Marked correct", 0),
    ],
    ids=["correct", "incorrect", "unanswered"],
)
def test_each_question_shows_its_verdict(
    logged_in_client, chosen, shown, hidden, learner_marks
):
    organisation = OrganisationFactory()
    form = _quiz()
    page = _form_page(form=form, order=1)
    question, options = _question(
        page, "Question A", 1, [("A one", True), ("A two", False)]
    )
    sitting = _paper_sitting(
        organisation,
        form,
        served_paper=served_paper_of([(page, [question])], {question: options}),
    )
    _answer(sitting, question, *[options[index] for index in chosen])

    text = _paper_text(
        _admin_client(organisation, logged_in_client), organisation, sitting
    )

    assert shown in text
    assert hidden not in text
    assert text.count("Learner's answer") == learner_marks


def test_a_free_text_question_shows_the_answer_and_not_marked(logged_in_client):
    organisation = OrganisationFactory()
    form = _quiz()
    page = _form_page(form=form, order=1)
    question = cast(
        FormQuestion,
        FormQuestionFactory(form_page=page, question="Explain", type="long_text"),
    )
    sitting = _paper_sitting(
        organisation, form, served_paper=served_paper_of([(page, [question])])
    )
    QuestionAnswerFactory(
        form_progress=sitting, question=question, text_answer="Because lift"
    )

    text = _paper_text(
        _admin_client(organisation, logged_in_client), organisation, sitting
    )

    assert "Because lift" in text
    assert "Not marked" in text
    assert "Did not answer" not in text


def test_the_paper_has_no_form_fields(logged_in_client):
    organisation = OrganisationFactory()
    form = _quiz()
    page = _form_page(form=form, order=1)
    choice, options = _question(page, "Question A", 1, [("A one", True)])
    dropdown = cast(
        FormQuestion,
        FormQuestionFactory(form_page=page, question="Pick", type="dropdown", order=2),
    )
    free_text = cast(
        FormQuestion,
        FormQuestionFactory(
            form_page=page, question="Explain", type="long_text", order=3
        ),
    )
    sitting = _paper_sitting(
        organisation,
        form,
        served_paper=served_paper_of(
            [(page, [choice, dropdown, free_text])], {choice: options, dropdown: []}
        ),
    )
    _answer(sitting, choice, *options)
    QuestionAnswerFactory(
        form_progress=sitting, question=free_text, text_answer="Because lift"
    )

    (paper,) = _page(
        _admin_client(organisation, logged_in_client), organisation, sitting
    ).cssselect("section[data-panel='paper']")

    assert paper.cssselect("input, select, textarea") == []


def test_a_correct_option_changed_after_submission_shows_the_stale_score_note(
    logged_in_client,
):
    organisation = OrganisationFactory()
    form = _quiz()
    page = _form_page(form=form, order=1)
    question, (one, two) = _question(
        page, "Question A", 1, [("A one", True), ("A two", False)]
    )
    sitting = _paper_sitting(
        organisation,
        form,
        served_paper=served_paper_of([(page, [question])], {question: [one, two]}),
        scores={"score": 1, "max_score": 1},
    )
    _answer(sitting, question, one)
    one.correct = False
    one.save()
    two.correct = True
    two.save()

    text = _paper_text(
        _admin_client(organisation, logged_in_client), organisation, sitting
    )

    assert "This quiz has changed since the attempt was marked." in text


def test_a_correct_option_added_after_submission_marks_the_question_incorrect(
    logged_in_client: Callable[[User], Client],
) -> None:
    organisation = OrganisationFactory()
    form = _quiz()
    page = _form_page(form=form, order=1)
    question, (one, two) = _question(
        page, "Question A", 1, [("A one", True), ("A two", False)]
    )
    sitting = _paper_sitting(
        organisation,
        form,
        served_paper=served_paper_of([(page, [question])], {question: [one, two]}),
        scores={"score": 1, "max_score": 1},
    )
    _answer(sitting, question, one)
    QuestionOptionFactory(question=question, text="A three", correct=True, order=2)

    text = _paper_text(
        _admin_client(organisation, logged_in_client), organisation, sitting
    )

    assert "This quiz has changed since the attempt was marked." in text
    assert "Marked incorrect" in text
    assert "Marked correct" not in text


def _sized_sitting(
    organisation: Organisation, page_count: int, questions_per_page: int
) -> FormProgress:
    form = _quiz()
    served: list[tuple[FormPage, list[FormQuestion | FormContent]]] = []
    options: dict[FormQuestion, list[QuestionOption]] = {}
    for number in range(page_count):
        page = _form_page(form=form, order=number)
        children: list[FormQuestion | FormContent] = []
        for index in range(questions_per_page):
            question, question_options = _question(
                page,
                f"Question {number}-{index}",
                index,
                [("Yes", True), ("No", False)],
            )
            children.append(question)
            options[question] = question_options
        served.append((page, children))
    sitting = _paper_sitting(
        organisation, form, served_paper=served_paper_of(served, options)
    )
    for question, question_options in options.items():
        _answer(sitting, question, question_options[0])
    return sitting


def test_a_thirty_question_paper_costs_no_more_queries_than_a_three_question_one(
    logged_in_client, django_assert_max_num_queries: DjangoAssertNumQueries
):
    organisation = OrganisationFactory()
    client = _admin_client(organisation, logged_in_client)
    small = _sized_sitting(organisation, 1, 3)
    large = _sized_sitting(organisation, 3, 10)
    with CaptureQueriesContext(connection) as baseline:
        client.get(_interface_url(organisation.slug, f"quiz-attempts/{small.pk}"))

    with django_assert_max_num_queries(len(baseline)):
        response = client.get(
            _interface_url(organisation.slug, f"quiz-attempts/{large.pk}")
        )

    assert response.status_code == 200


def test_the_quick_view_shows_the_title_the_subtitle_six_rows_and_no_link_in_its_body(
    logged_in_client,
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(
        organisation=organisation, user__first_name="Ada", user__last_name="Lovelace"
    )
    sitting = _sitting(learner)

    response = _get_quick_view(
        _admin_client(organisation, logged_in_client),
        organisation,
        f"quiz-attempts/{sitting.pk}",
    )

    assert response.status_code == 200
    document = lxml.html.fromstring(response.content.decode())
    (frame,) = document.cssselect("[data-quick-view-title]")
    assert frame.get("data-quick-view-title") == "Safety quiz, attempt 1"
    assert frame.get("data-quick-view-subtitle") == "Ada Lovelace"
    assert [_text(label) for label in document.cssselect("dt")] == [
        "Result",
        "Score",
        "Percentage",
        "Pass mark (current setting)",
        "Started",
        "Completed",
    ]
    # The quick view header's "Open full page" icon is the one link to the
    # review page. The body used to add a second one.
    assert document.cssselect("a") == []


def test_the_quick_view_of_a_quiz_with_no_pass_mark_says_so(logged_in_client):
    organisation = OrganisationFactory()
    sitting = _sitting(LearnerFactory(organisation=organisation), pass_percentage=None)

    response = _get_quick_view(
        _admin_client(organisation, logged_in_client),
        organisation,
        f"quiz-attempts/{sitting.pk}",
    )

    text = _text(lxml.html.fromstring(response.content.decode()))
    assert text.count("No pass mark") == 2


def test_a_quick_view_request_that_is_not_htmx_redirects_to_the_page(logged_in_client):
    organisation = OrganisationFactory()
    sitting = _sitting(LearnerFactory(organisation=organisation))
    page = _interface_url(organisation.slug, f"quiz-attempts/{sitting.pk}")

    response = _admin_client(organisation, logged_in_client).get(f"{page}/__quick-view")

    assert response.status_code == 302
    assert response["Location"] == page
