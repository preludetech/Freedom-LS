"""Builders shared by the course_applications tests."""

import threading
from collections.abc import Callable
from datetime import datetime
from typing import NamedTuple, cast

from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sites.models import Site
from django.db import connection
from django.http import HttpRequest
from django.test import RequestFactory
from django.urls import reverse
from rest_framework.test import APIClient

from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.course_applications.anonymous_session import (
    remember_anonymous_applicant,
)
from freedom_ls.course_applications.factories import CourseApplicationFactory
from freedom_ls.course_applications.models import (
    AnonymousApplicant,
    CourseApplication,
)
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormProgressFactory,
    FormQuestionFactory,
    QuestionAnswerFactory,
    QuestionAnswerFileFactory,
    QuestionOptionFactory,
)
from freedom_ls.form_engine.models import FormProgress, FormStrategy
from freedom_ls.tests.site_context import site_context


def _add_employer_case(form: FormFactory, page_one: FormPageFactory) -> None:
    """Add the employer question to page 1 and, on page 2, a page only a Yes opens."""
    employer_pays = FormQuestionFactory(
        form_page=page_one,
        type="multiple_choice",
        order=4,
        slug="employer_pays",
        question="Is your employer paying",
        required=False,
    )
    employer_yes = QuestionOptionFactory(
        question=employer_pays, text="Yes", value="yes", order=0
    )
    QuestionOptionFactory(question=employer_pays, text="No", value="no", order=1)
    employer_page = FormPageFactory(
        form=form, order=1, title="Your employer", condition_option=employer_yes
    )
    FormQuestionFactory(
        form_page=employer_page,
        type="short_text",
        order=0,
        question="Employer name",
        required=True,
    )


def gated_course_with_form(
    *, with_employer_case: bool = False
) -> tuple[CourseFactory, FormFactory]:
    """An application-gated course whose applicants fill in a form.

    Page 1 carries one question of each non-file type; the last page carries the
    file question, so a test can reach a page that needs a real upload without
    the first page demanding one. With `with_employer_case` page 1 also asks
    whether an employer is paying, and a "Your employer" page between the two
    applies only to applicants who answer Yes.
    """
    form = FormFactory(strategy=FormStrategy.UNSCORED)

    page_one = FormPageFactory(form=form, order=0, title="About you")
    FormQuestionFactory(
        form_page=page_one,
        type="short_text",
        order=0,
        question="Your name",
        required=True,
    )
    FormQuestionFactory(
        form_page=page_one,
        type="number",
        order=1,
        question="Years of experience",
        required=False,
    )
    choice = FormQuestionFactory(
        form_page=page_one,
        type="multiple_choice",
        order=2,
        question="How did you hear about us",
        required=False,
    )
    QuestionOptionFactory(question=choice, text="A friend", order=0)
    QuestionOptionFactory(question=choice, text="Search", order=1)
    FormQuestionFactory(
        form_page=page_one,
        type="long_text",
        order=3,
        question="Why apply",
        required=False,
    )
    if with_employer_case:
        _add_employer_case(form, page_one)

    documents_page = FormPageFactory(
        form=form, order=2 if with_employer_case else 1, title="Supporting documents"
    )
    FormQuestionFactory(
        form_page=documents_page,
        type="file_upload",
        order=0,
        question="Upload your ID",
        required=False,
    )

    course = CourseFactory(access_config={"access_type": "application_gated"})
    course.application_form = form
    course.save(update_fields=["application_form"])
    return course, form


class UnverifiedApplication(NamedTuple):
    """An unverified application with its applicant and its sitting."""

    application: CourseApplication
    applicant: AnonymousApplicant
    sitting: FormProgress


def unverified_application_with_file() -> UnverifiedApplication:
    """An unverified application whose sitting holds one answer with a stored file."""
    application = cast(
        CourseApplication,
        CourseApplicationFactory(
            anonymous=True, form_progress=FormProgressFactory(user=None)
        ),
    )
    assert application.anonymous_applicant is not None
    assert application.form_progress is not None
    QuestionAnswerFileFactory(
        answer=QuestionAnswerFactory(form_progress=application.form_progress)
    )
    return UnverifiedApplication(
        application, application.anonymous_applicant, application.form_progress
    )


def anonymous_request_holding(*applicants: AnonymousApplicant) -> HttpRequest:
    """An anonymous request whose session remembers each applicant."""
    request = RequestFactory().get("/")
    request.user = AnonymousUser()
    request.session = SessionStore()
    for applicant in applicants:
        remember_anonymous_applicant(request, applicant)
    return request


def application_ids_updated_since(auth: dict[str, str], since: datetime) -> list[str]:
    """The ids the applications API lists for an `updated_since` poll at `since`."""
    response = APIClient().get(
        reverse("api:course_application_list"),
        {"updated_since": since.isoformat()},
        headers=auth,
    )
    return [row["id"] for row in response.json()["results"]]


def run_in_parallel_threads(
    site: Site, action: Callable[[], object], count: int
) -> list[BaseException | None]:
    """Run `action` in `count` threads at once, each on its own database
    connection and inside `site`'s context, and return what each raised.

    The entry for a thread whose call returned is None. A barrier releases the
    threads together so their calls overlap.
    """
    barrier = threading.Barrier(count)
    outcomes: list[BaseException | None] = [None] * count

    def run(index: int) -> None:
        try:
            with site_context(site):
                barrier.wait(timeout=5)
                action()
        except BaseException as exc:
            outcomes[index] = exc
        finally:
            connection.close()

    threads = [threading.Thread(target=run, args=(i,)) for i in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)
    return outcomes
