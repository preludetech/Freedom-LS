"""The declaration page a learner signs before each attempt at a declaration quiz,
and form_start's hand-off to it."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import cast

import lxml.html
import pytest
import time_machine

from django.http import HttpResponse
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.content_engine.models import Course
from freedom_ls.content_engine.tests.helpers import collection_item_for
from freedom_ls.deadlines.actions import resume_course
from freedom_ls.deadlines.factories import (
    CourseDeadlineConfigFactory,
    CoursePauseFactory,
)
from freedom_ls.form_engine.declarations import declaration_text_hash
from freedom_ls.form_engine.factories import (
    FormDeclarationFactory,
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
    QuestionOptionFactory,
)
from freedom_ls.form_engine.models import (
    Form,
    FormDeclaration,
    FormProgress,
    FormStrategy,
)
from freedom_ls.learner_interface.tests.helpers import (
    course_with_form,
    form_attempt,
    set_due_date,
    topic_completion,
)
from freedom_ls.learner_management.tests.helpers import register_user_for_course
from freedom_ls.learner_progress.attempts import (
    START_REUSE_WINDOW,
    get_latest_incomplete,
)
from freedom_ls.learner_progress.models import CourseFormAttempt
from freedom_ls.learner_progress.tests.helpers import course_progress_record

AFTER_CLOSE = datetime(2020, 1, 10, 12, 0, tzinfo=UTC)


def _declaration_quiz(
    *, submit_on_exit: bool = False, declaration_text: str = "", **fields: object
) -> Form:
    """A one-page quiz that asks for a declaration before every attempt."""
    form: Form = FormFactory(
        strategy=FormStrategy.QUIZ,
        quiz_pass_percentage=70,
        requires_declaration=True,
        declaration_text=declaration_text,
        submit_on_exit=submit_on_exit,
        **fields,
    )
    page = FormPageFactory(form=form, order=0)
    question = FormQuestionFactory(form_page=page, type="multiple_choice", order=0)
    QuestionOptionFactory(question=question, correct=True)
    QuestionOptionFactory(question=question, correct=False)
    return form


def _kwargs(course: Course, index: int = 1) -> dict[str, object]:
    return {"course_slug": course.slug, "index": index}


def _declaration_url(course: Course, index: int = 1) -> str:
    return reverse("learner_interface:form_declaration", kwargs=_kwargs(course, index))


def _start_url(course: Course, index: int = 1) -> str:
    return reverse("learner_interface:form_start", kwargs=_kwargs(course, index))


def _page_one_url(course: Course, index: int = 1) -> str:
    return reverse(
        "learner_interface:form_fill_page",
        kwargs={**_kwargs(course, index), "page_number": 1},
    )


def _signature(form: Form, **overrides: str) -> dict[str, str]:
    return {
        "agreed": "on",
        "typed_name": "Thandi Nkosi",
        "text_hash": declaration_text_hash(form.effective_declaration_text()),
        **overrides,
    }


@pytest.fixture
def declaration_course(
    mock_site_context: object, client: Client
) -> tuple[Course, Form, User]:
    """A registered, logged-in learner's course whose only item is a declaration quiz."""
    user: User = UserFactory()
    form = _declaration_quiz()
    course = course_with_form(form)
    register_user_for_course(course, user)
    client.force_login(user)
    return course, form, user


def _location(response: HttpResponse) -> str:
    return cast("str", response["Location"])


def _sittings() -> tuple[int, int, int]:
    return (
        FormProgress.objects.count(),
        CourseFormAttempt.objects.count(),
        FormDeclaration.objects.count(),
    )


@pytest.mark.django_db
def test_form_start_on_a_declaration_quiz_with_no_open_sitting_redirects_to_the_declaration_and_writes_nothing(
    declaration_course, client
):
    course, _form, _user = declaration_course

    response = client.get(_start_url(course))

    assert _location(response) == _declaration_url(course)
    assert _sittings() == (0, 0, 0)


@pytest.mark.django_db
def test_form_start_resumes_a_signed_open_sitting(declaration_course, client):
    course, form, user = declaration_course
    sitting = form_attempt(course, user, form)
    FormDeclarationFactory(form_progress=sitting)

    response = client.get(_start_url(course))

    assert _location(response) == _page_one_url(course)
    assert FormProgress.objects.get().pk == sitting.pk


@pytest.mark.django_db
def test_form_start_redirects_an_unsigned_open_sitting_to_the_declaration(
    declaration_course, client
):
    course, form, user = declaration_course
    sitting = form_attempt(course, user, form)

    response = client.get(_start_url(course))

    assert _location(response) == _declaration_url(course)
    sitting.refresh_from_db()
    assert sitting.completed_time is None


@pytest.mark.django_db
def test_form_start_neither_finalises_nor_replaces_a_signed_idle_submit_on_exit_sitting(
    mock_site_context, client
):
    user = UserFactory()
    form = _declaration_quiz(submit_on_exit=True)
    course = course_with_form(form)
    register_user_for_course(course, user)
    client.force_login(user)
    sitting = form_attempt(course, user, form)
    FormDeclarationFactory(form_progress=sitting)
    FormProgress.objects.filter(pk=sitting.pk).update(
        start_time=timezone.now() - START_REUSE_WINDOW - timedelta(seconds=1)
    )

    client.get(_start_url(course))

    sitting.refresh_from_db()
    assert sitting.completed_time is None
    assert FormProgress.objects.count() == 1


@pytest.mark.django_db
def test_form_start_on_a_quiz_without_the_flag_starts_a_sitting_as_before(
    mock_site_context, client
):
    user = UserFactory()
    form = _declaration_quiz()
    form.requires_declaration = False
    form.save()
    course = course_with_form(form)
    register_user_for_course(course, user)
    client.force_login(user)

    response = client.get(_start_url(course))

    assert _location(response) == _page_one_url(course)
    assert _sittings() == (1, 1, 0)


@pytest.mark.django_db
def test_form_start_on_a_survey_starts_a_sitting_as_before(mock_site_context, client):
    user = UserFactory()
    form = FormFactory(strategy=FormStrategy.CATEGORY_VALUE_SUM)
    FormPageFactory(form=form, order=0)
    course = course_with_form(form)
    register_user_for_course(course, user)
    client.force_login(user)

    response = client.get(_start_url(course))

    assert _location(response) == _page_one_url(course)
    assert _sittings() == (1, 1, 0)


@pytest.mark.django_db
def test_the_page_shows_the_effective_declaration_text(declaration_course, client):
    course, form, _user = declaration_course

    response = client.get(_declaration_url(course))

    document = lxml.html.fromstring(response.content)
    [shown] = document.xpath('//*[@data-testid="declaration-text"]')
    assert form.effective_declaration_text() in shown.text_content()


@pytest.mark.django_db
def test_the_page_escapes_the_authors_declaration_text(mock_site_context, client):
    user = UserFactory()
    form = _declaration_quiz(declaration_text="Honest <script>alert(1)</script> work.")
    course = course_with_form(form)
    register_user_for_course(course, user)
    client.force_login(user)

    response = client.get(_declaration_url(course))

    assert b"<script>alert(1)" not in response.content
    document = lxml.html.fromstring(response.content)
    [shown] = document.xpath('//*[@data-testid="declaration-text"]')
    assert "<script>alert(1)</script>" in shown.text_content()


@pytest.mark.django_db
def test_the_page_offers_an_empty_name_field_that_asks_the_browser_for_a_name(
    declaration_course, client
):
    course, _form, _user = declaration_course

    response = client.get(_declaration_url(course))

    document = lxml.html.fromstring(response.content)
    [name_input] = document.xpath('//*[@data-testid="declaration-typed-name"]')
    assert name_input.get("autocomplete") == "name"
    assert name_input.get("value") is None


@pytest.mark.django_db
def test_the_page_carries_the_hash_of_the_text_it_shows(declaration_course, client):
    course, form, _user = declaration_course

    response = client.get(_declaration_url(course))

    document = lxml.html.fromstring(response.content)
    [hidden] = document.xpath('//input[@name="text_hash"]')
    assert hidden.get("value") == declaration_text_hash(
        form.effective_declaration_text()
    )


@pytest.mark.django_db
def test_a_valid_signature_stores_the_declaration_as_rendered_and_opens_page_one(
    declaration_course, client
):
    course, form, user = declaration_course

    response = client.post(
        _declaration_url(course),
        _signature(form, typed_name="  Thandi Nkosi "),
        REMOTE_ADDR="203.0.113.7",
    )

    assert _location(response) == _page_one_url(course)
    declaration = FormDeclaration.objects.get()
    assert declaration.declaration_text == form.effective_declaration_text()
    assert declaration.typed_name == "  Thandi Nkosi "
    assert declaration.ip_address == "203.0.113.7"
    assert declaration.form_progress.user == user
    assert declaration.site_id == declaration.form_progress.site_id


@pytest.mark.django_db
def test_a_valid_signature_writes_the_served_paper(declaration_course, client):
    course, form, _user = declaration_course

    client.post(_declaration_url(course), _signature(form))

    assert FormProgress.objects.get().served_paper is not None


@pytest.mark.django_db
def test_a_repeated_post_of_one_signature_stores_one_declaration(
    declaration_course, client
):
    course, form, _user = declaration_course

    client.post(_declaration_url(course), _signature(form))
    client.post(_declaration_url(course), _signature(form))

    assert _sittings() == (1, 1, 1)


@pytest.mark.django_db
def test_try_again_after_a_completed_attempt_asks_for_a_second_signature(
    declaration_course, client
):
    course, form, user = declaration_course
    client.post(_declaration_url(course), _signature(form))
    first = FormProgress.objects.get()
    first.complete()

    response = client.get(_start_url(course))
    assert _location(response) == _declaration_url(course)
    client.post(_declaration_url(course), _signature(form, typed_name="Thandi N"))

    assert FormDeclaration.objects.count() == 2
    second = get_latest_incomplete(
        course_progress_record(course, user), collection_item_for(course, form)
    )
    assert second is not None
    assert second.pk != first.pk
    assert second.declaration.typed_name == "Thandi N"


@pytest.mark.django_db
def test_a_paused_submit_on_exit_sitting_signed_through_the_declaration_is_kept(
    mock_site_context,
):
    user = UserFactory()
    course = CourseFactory()
    course.items.create(child=TopicFactory(), order=0)
    form = _declaration_quiz(submit_on_exit=True)
    course.items.create(child=form, order=1)
    record = course_progress_record(course, user)
    sitting = form_attempt(course, user, form)
    FormProgress.objects.filter(pk=sitting.pk).update(
        start_time=timezone.now() - START_REUSE_WINDOW - timedelta(seconds=1)
    )
    CoursePauseFactory(course_progress=record, started_at=timezone.now())
    resume_course(record, actor=None, reason="Back")
    client = Client()
    client.force_login(user)
    topic_completion(
        course, user, course.viewable_items()[0], complete_time=timezone.now()
    )

    client.post(_declaration_url(course, 2), _signature(form))

    sitting.refresh_from_db()
    assert sitting.completed_time is None
    assert FormDeclaration.objects.get().form_progress == sitting


@pytest.mark.django_db
def test_a_missing_trusted_proxy_header_refuses_the_signature_and_writes_nothing(
    declaration_course, client, settings
):
    course, form, _user = declaration_course
    settings.TRUSTED_PROXY_IP_HEADER = "X-Real-IP"

    response = client.post(_declaration_url(course), _signature(form))

    assert response.status_code == 403
    assert _sittings() == (0, 0, 0)


@pytest.mark.django_db
@pytest.mark.parametrize("method", ["get", "post"])
def test_a_blocked_item_is_redirected_as_form_start_redirects_it(
    mock_site_context, client, method
):
    user = UserFactory()
    course = CourseFactory()
    course.items.create(child=TopicFactory(), order=0)
    form = _declaration_quiz()
    course.items.create(child=form, order=1)
    register_user_for_course(course, user)
    client.force_login(user)

    response = getattr(client, method)(_declaration_url(course, 2))

    assert _location(response) == _location(client.get(_start_url(course, 2)))
    assert _location(response) != _declaration_url(course, 2)
    assert _sittings() == (0, 0, 0)


@pytest.mark.django_db
@pytest.mark.parametrize("method", ["get", "post"])
@time_machine.travel(AFTER_CLOSE, tick=False)
def test_a_closed_item_is_redirected_as_form_start_redirects_it(
    mock_site_context, client, method
):
    user = UserFactory()
    form = _declaration_quiz()
    course = course_with_form(form)
    register_user_for_course(course, user)
    set_due_date(course, form, due_date=date(2020, 1, 1))
    CourseDeadlineConfigFactory(course=course, close_items="on")
    client.force_login(user)

    response = getattr(client, method)(_declaration_url(course))

    assert _location(response) == _location(client.get(_start_url(course)))
    assert _location(response) != _declaration_url(course)
    assert _sittings() == (0, 0, 0)


@pytest.mark.django_db
@pytest.mark.parametrize("method", ["get", "post"])
def test_a_learner_without_access_is_redirected_as_form_start_redirects_them(
    mock_site_context, client, method
):
    form = _declaration_quiz()
    course = course_with_form(form)
    client.force_login(UserFactory())

    response = getattr(client, method)(_declaration_url(course))

    assert _location(response) == _location(client.get(_start_url(course)))
    assert _location(response) != _declaration_url(course)
    assert _sittings() == (0, 0, 0)


@pytest.mark.django_db
def test_a_quiz_without_the_flag_redirects_to_form_start(mock_site_context, client):
    user = UserFactory()
    form = _declaration_quiz()
    form.requires_declaration = False
    form.save()
    course = course_with_form(form)
    register_user_for_course(course, user)
    client.force_login(user)

    response = client.get(_declaration_url(course))

    assert _location(response) == _start_url(course)


@pytest.mark.django_db
def test_a_survey_redirects_to_form_start(mock_site_context, client):
    user = UserFactory()
    form = FormFactory(strategy=FormStrategy.CATEGORY_VALUE_SUM)
    course = course_with_form(form)
    register_user_for_course(course, user)
    client.force_login(user)

    response = client.get(_declaration_url(course))

    assert _location(response) == _start_url(course)


def _rejected_page(
    declaration_course: tuple[Course, Form, User],
    client: Client,
    **overrides: str,
) -> tuple[int, lxml.html.HtmlElement]:
    course, form, _user = declaration_course
    response = client.post(_declaration_url(course), _signature(form, **overrides))
    return response.status_code, lxml.html.fromstring(response.content)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"agreed": ""}, id="unticked_box"),
        pytest.param({"typed_name": ""}, id="blank_name"),
        pytest.param({"typed_name": "   "}, id="whitespace_name"),
        pytest.param({"text_hash": "stale"}, id="stale_hash"),
    ],
)
def test_a_rejected_signature_returns_422_and_stores_nothing(
    declaration_course, client, overrides
):
    status, _document = _rejected_page(declaration_course, client, **overrides)

    assert status == 422
    assert _sittings() == (0, 0, 0)


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("overrides", "field_id", "error_id"),
    [
        pytest.param({"agreed": ""}, "id_agreed", "agreed-error", id="unticked_box"),
        pytest.param(
            {"typed_name": ""}, "id_typed_name", "typed_name-error", id="blank_name"
        ),
        pytest.param(
            {"typed_name": "   "},
            "id_typed_name",
            "typed_name-error",
            id="whitespace_name",
        ),
    ],
)
def test_a_field_error_is_linked_to_its_input_and_takes_focus(
    declaration_course, client, overrides, field_id, error_id
):
    _response, document = _rejected_page(declaration_course, client, **overrides)

    [error] = document.xpath(f'//*[@id="{error_id}"]')
    assert error.text_content().strip()
    [field] = document.xpath(f'//*[@id="{field_id}"]')
    assert field.get("aria-invalid") == "true"
    assert error_id in field.get("aria-describedby").split()
    assert field.get("autofocus") is not None


@pytest.mark.django_db
def test_the_first_field_in_error_alone_takes_focus(declaration_course, client):
    _response, document = _rejected_page(
        declaration_course, client, agreed="", typed_name=""
    )

    [focused] = document.xpath("//*[@autofocus]")
    assert focused.get("id") == "id_agreed"


@pytest.mark.django_db
def test_a_rejected_box_keeps_the_typed_name(declaration_course, client):
    _response, document = _rejected_page(declaration_course, client, agreed="")

    [name] = document.xpath('//*[@id="id_typed_name"]')
    assert name.get("value") == "Thandi Nkosi"


@pytest.mark.django_db
def test_a_rejected_name_keeps_the_box_ticked(declaration_course, client):
    _response, document = _rejected_page(declaration_course, client, typed_name=" ")

    [box] = document.xpath('//*[@id="id_agreed"]')
    assert box.get("checked") is not None


@pytest.mark.django_db
def test_a_stale_text_hash_explains_the_change_and_clears_both_fields(
    declaration_course, client
):
    _course, form, _user = declaration_course

    _response, document = _rejected_page(declaration_course, client, text_hash="stale")

    assert document.xpath('//*[@data-testid="declaration-changed"]')
    [box] = document.xpath('//*[@id="id_agreed"]')
    [name] = document.xpath('//*[@id="id_typed_name"]')
    [hidden] = document.xpath('//input[@name="text_hash"]')
    assert box.get("checked") is None
    assert name.get("value") is None
    assert hidden.get("value") == declaration_text_hash(
        form.effective_declaration_text()
    )


@pytest.mark.django_db
def test_a_field_error_shows_no_changed_callout(declaration_course, client):
    _response, document = _rejected_page(declaration_course, client, agreed="")

    assert not document.xpath('//*[@data-testid="declaration-changed"]')
