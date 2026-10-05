"""The form_engine admin: who may open, add to and delete from it."""

from __future__ import annotations

import re

import pytest

from django.contrib import admin
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.form_engine.admin import (
    FormAdmin,
    FormContentAdmin,
    FormPageAdmin,
    FormQuestionAdmin,
    QuestionAnswerAdmin,
    QuestionOptionAdmin,
)
from freedom_ls.form_engine.enums import QuestionType
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormProgressFactory,
    FormQuestionFactory,
    QuestionAnswerFactory,
    QuestionAnswerFileFactory,
    QuestionOptionFactory,
)
from freedom_ls.form_engine.models import (
    Form,
    FormContent,
    FormPage,
    FormQuestion,
    FormStrategy,
    QuestionAnswer,
    QuestionOption,
)
from freedom_ls.form_engine.queries import FINAL_GROUP_TITLE

CHANGE_URL_NAME = "admin:freedom_ls_form_engine_formprogress_change"


@pytest.mark.django_db
def test_completed_time_is_not_editable(staff_client):
    """Only FormProgress.complete() may finish an attempt.

    It scores the attempt and sends form_attempt_completed, which is what keeps
    CourseProgress.progress_percentage current. An admin stamping completed_time
    by hand would leave both stale, so the field must not reach the form.
    """
    progress = FormProgressFactory()

    response = staff_client.get(reverse(CHANGE_URL_NAME, args=[progress.pk]))

    assert "completed_time" not in response.context["adminform"].form.fields


FORM_ADMINS = [
    (FormAdmin, Form),
    (FormPageAdmin, FormPage),
    (FormContentAdmin, FormContent),
    (FormQuestionAdmin, FormQuestion),
    (QuestionOptionAdmin, QuestionOption),
]


@pytest.mark.parametrize(
    ("admin_class", "model"),
    FORM_ADMINS,
    ids=[model.__name__ for _, model in FORM_ADMINS],
)
def test_form_admins_never_permit_deletion(admin_class, model) -> None:
    assert admin_class(model, admin.site).has_delete_permission(request=None) is False


@pytest.mark.django_db
class TestTheLockdownReachesTheAdminUi:
    """A superuser -- who holds every Django permission -- still cannot delete.

    `has_delete_permission` returning False is only worth anything if it is what
    the admin actually consults, so these go through HTTP rather than call it.
    """

    def test_the_change_page_offers_no_delete_link(self, staff_client) -> None:
        form = FormFactory()

        response = staff_client.get(
            reverse("admin:freedom_ls_form_engine_form_change", args=[form.pk])
        )

        delete_url = reverse("admin:freedom_ls_form_engine_form_delete", args=[form.pk])
        assert delete_url not in response.content.decode()

    def test_posting_the_delete_url_leaves_the_form_standing(
        self, staff_client
    ) -> None:
        form = FormFactory()

        response = staff_client.post(
            reverse("admin:freedom_ls_form_engine_form_delete", args=[form.pk]),
            {"post": "yes"},
        )

        assert response.status_code == 403
        assert Form.objects.filter(pk=form.pk).exists()

    def test_the_change_page_offers_no_inline_delete_checkbox(
        self, staff_client
    ) -> None:
        """A page is removed by editing the form, never by a stray tick."""
        form = FormFactory()

        response = staff_client.get(
            reverse("admin:freedom_ls_form_engine_form_change", args=[form.pk])
        )

        assert not re.search(r'name="[^"]*-DELETE"', response.content.decode())


@pytest.mark.django_db
class TestFormProgressChangelist:
    """The changelist that answers "who has finished this form, and when"."""

    CHANGELIST_URL_NAME = "admin:freedom_ls_form_engine_formprogress_changelist"

    def test_it_renders_with_rows_present(self, staff_client) -> None:
        FormProgressFactory()

        response = staff_client.get(reverse(self.CHANGELIST_URL_NAME))

        assert response.status_code == 200

    def test_the_completion_filter_separates_finished_from_unfinished(
        self, staff_client
    ) -> None:
        finished = FormProgressFactory(completed_time=timezone.now())
        unfinished = FormProgressFactory(completed_time=None)
        url = reverse(self.CHANGELIST_URL_NAME)

        def visible(completion: str) -> list:
            response = staff_client.get(url, {"completion": completion})
            return [row.pk for row in response.context["cl"].result_list]

        assert visible("complete") == [finished.pk]
        assert visible("incomplete") == [unfinished.pk]


# ---------------------------------------------------------------------------
# Answer data is gated by view permissions
# ---------------------------------------------------------------------------


@pytest.fixture
def viewer_client(mock_site_context, logged_in_client):
    """Staff holding only the three form_engine view permissions."""
    viewer = UserFactory(is_staff=True, is_superuser=False)
    viewer.user_permissions.set(
        Permission.objects.filter(
            content_type__app_label="freedom_ls_form_engine",
            codename__in=[
                "view_formprogress",
                "view_questionanswer",
                "view_questionanswerfile",
            ],
        )
    )
    return logged_in_client(viewer)


@pytest.fixture
def no_permission_client(mock_site_context, logged_in_client):
    """Staff holding no permissions at all."""
    return logged_in_client(UserFactory(is_staff=True, is_superuser=False))


ANSWER_CHANGELISTS = [
    "admin:freedom_ls_form_engine_questionanswer_changelist",
    "admin:freedom_ls_form_engine_formprogress_changelist",
    "admin:freedom_ls_form_engine_questionanswerfile_changelist",
]


@pytest.mark.django_db
@pytest.mark.parametrize("url_name", ANSWER_CHANGELISTS)
def test_staff_without_permission_cannot_reach_answer_data(
    no_permission_client, url_name
):
    response = no_permission_client.get(reverse(url_name))

    assert response.status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize("url_name", ANSWER_CHANGELISTS)
def test_a_viewer_can_reach_answer_data(viewer_client, url_name):
    response = viewer_client.get(reverse(url_name))

    assert response.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize("url_name", ANSWER_CHANGELISTS)
def test_a_superuser_can_reach_answer_data(staff_client, url_name):
    response = staff_client.get(reverse(url_name))

    assert response.status_code == 200


ANSWER_MODELS = ["questionanswer", "formprogress", "questionanswerfile"]

ANSWER_FACTORIES = {
    "questionanswer": QuestionAnswerFactory,
    "formprogress": FormProgressFactory,
    "questionanswerfile": QuestionAnswerFileFactory,
}


@pytest.mark.django_db
@pytest.mark.parametrize("model_name", ANSWER_MODELS)
def test_a_viewer_cannot_add_answer_data(viewer_client, model_name):
    """Django's add view consults only has_add_permission, so a view permission
    must not be enough to fabricate an answer."""
    response = viewer_client.get(
        reverse(f"admin:freedom_ls_form_engine_{model_name}_add")
    )

    assert response.status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize("model_name", ANSWER_MODELS)
def test_a_viewer_cannot_delete_answer_data(viewer_client, model_name):
    """Django's delete view consults only has_delete_permission, so a view
    permission must not be enough to destroy an applicant's ID scan."""
    row = ANSWER_FACTORIES[model_name]()

    response = viewer_client.post(
        reverse(f"admin:freedom_ls_form_engine_{model_name}_delete", args=[row.pk]),
        {"post": "yes"},
    )

    assert response.status_code == 403
    assert type(row)._base_manager.filter(pk=row.pk).exists()


@pytest.mark.django_db
def test_the_admin_index_lists_no_answer_data_without_permission(
    no_permission_client,
):
    """A model with any one of add, change, delete or view still gets an index
    entry, so all four have to be denied for the listing to go."""
    response = no_permission_client.get(reverse("admin:index"))

    body = response.content.decode()
    assert not any(reverse(url_name) in body for url_name in ANSWER_CHANGELISTS)


# ---------------------------------------------------------------------------
# Slug minting
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_two_forms_added_with_no_slug_both_save(staff_client):
    """The slug is read-only in the admin, so nothing can supply one by hand and
    the second form of the same title would otherwise collide.
    """
    add_url = reverse("admin:freedom_ls_form_engine_form_add")
    payload = {
        "title": "Application form",
        "subtitle": "",
        "description": "",
        "content": "",
        "strategy": FormStrategy.UNSCORED,
        "meta": "null",
        "tags": "",
        "pages-TOTAL_FORMS": "0",
        "pages-INITIAL_FORMS": "0",
        "pages-MIN_NUM_FORMS": "0",
        "pages-MAX_NUM_FORMS": "1000",
    }

    staff_client.post(add_url, payload)
    staff_client.post(add_url, payload)

    slugs = set(
        Form.objects.filter(title="Application form").values_list("slug", flat=True)
    )
    assert len(slugs) == 2


# ---------------------------------------------------------------------------
# The admin download route
# ---------------------------------------------------------------------------


def _admin_download_url(answer_file) -> str:
    return reverse(
        "admin:freedom_ls_form_engine_questionanswerfile_download",
        args=[answer_file.pk],
    )


@pytest.mark.django_db
def test_staff_without_permission_cannot_download_an_answer_file(
    mock_site_context, no_permission_client
):
    answer_file = QuestionAnswerFileFactory()

    response = no_permission_client.get(_admin_download_url(answer_file))

    assert response.status_code == 403


@pytest.mark.django_db
def test_an_answer_file_is_served_to_a_viewer(mock_site_context, viewer_client):
    answer_file = QuestionAnswerFileFactory()

    response = viewer_client.get(_admin_download_url(answer_file))

    assert response.status_code == 200


@pytest.mark.django_db
def test_an_answer_file_is_served_to_a_superuser(mock_site_context, staff_client):
    answer_file = QuestionAnswerFileFactory()

    response = staff_client.get(_admin_download_url(answer_file))

    assert response.status_code == 200


@pytest.mark.django_db
def test_the_changelist_offers_a_download(mock_site_context, staff_client):
    answer_file = QuestionAnswerFileFactory()

    response = staff_client.get(
        reverse("admin:freedom_ls_form_engine_questionanswerfile_changelist")
    )

    assert _admin_download_url(answer_file) in response.content.decode()


# ---------------------------------------------------------------------------
# answer_preview renders a stored answer the way a reader would see it
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_answer_preview_renders_a_date_answer_for_a_reader(mock_site_context) -> None:
    question = FormQuestionFactory(type=QuestionType.DATE)
    answer = QuestionAnswerFactory(question=question, text_answer="1987-03-14")

    preview = QuestionAnswerAdmin(QuestionAnswer, admin.site).answer_preview(answer)

    assert preview == "March 14, 1987"


@pytest.mark.django_db
def test_answer_preview_truncates_a_long_answer_to_fifty_characters(
    mock_site_context,
) -> None:
    question = FormQuestionFactory(type=QuestionType.SHORT_TEXT)
    answer = QuestionAnswerFactory(question=question, text_answer="x" * 60)

    preview = QuestionAnswerAdmin(QuestionAnswer, admin.site).answer_preview(answer)

    assert preview == "x" * 50


# ---------------------------------------------------------------------------
# Bounds set by hand are validated, not left inert
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_a_bound_that_does_not_parse_is_refused_by_the_model(mock_site_context) -> None:
    """`31/12/2010` renders straight into the `max` attribute, where the
    browser ignores it as an invalid date and the runtime check parses it to
    None and skips it. Inert either way, so it must not be storable."""
    question = FormQuestionFactory(type=QuestionType.DATE, max="31/12/2010")

    with pytest.raises(ValidationError):
        question.clean()


@pytest.mark.django_db
def test_a_bound_on_a_type_with_no_order_is_refused_by_the_model(
    mock_site_context,
) -> None:
    """YAML forbids this; the admin must not be the way around it."""
    question = FormQuestionFactory(type=QuestionType.SHORT_TEXT, min="1")

    with pytest.raises(ValidationError):
        question.clean()


@pytest.mark.django_db
def test_decimal_places_on_a_type_that_is_not_a_number_is_refused_by_the_model(
    mock_site_context,
) -> None:
    question = FormQuestionFactory(type=QuestionType.SHORT_TEXT, decimal_places=2)

    with pytest.raises(ValidationError):
        question.clean()


@pytest.mark.django_db
def test_a_valid_bound_passes_the_model_check(mock_site_context) -> None:
    question = FormQuestionFactory(type=QuestionType.DATE, max="2010-01-01")

    question.clean()


def _change_payload(response, **overrides: str) -> dict[str, str]:
    """The admin change form's own values, ready to post straight back."""
    form = response.context["adminform"].form
    payload = {
        name: "" if form.initial.get(name) is None else str(form.initial.get(name, ""))
        for name in form.fields
    }
    for inline in response.context["inline_admin_formsets"]:
        prefix = inline.formset.prefix
        payload[f"{prefix}-TOTAL_FORMS"] = "0"
        payload[f"{prefix}-INITIAL_FORMS"] = "0"
        payload[f"{prefix}-MIN_NUM_FORMS"] = "0"
        payload[f"{prefix}-MAX_NUM_FORMS"] = "1000"
    payload.update(overrides)
    return payload


@pytest.fixture
def date_question(mock_site_context) -> FormQuestion:
    """A date question complete enough for the admin change form to accept it."""
    question: FormQuestion = FormQuestionFactory(
        type=QuestionType.DATE,
        max="",
        file_path="forms/application/1. about-you.yaml",
    )
    return question


def _question_change_url(question: FormQuestion) -> str:
    return reverse(
        "admin:freedom_ls_form_engine_formquestion_change", args=[question.pk]
    )


@pytest.mark.django_db
def test_the_admin_refuses_a_bound_that_does_not_parse(
    staff_client, date_question
) -> None:
    """The model check is only worth anything if it is what the admin consults,
    so this goes through HTTP rather than calling `clean()`."""
    url = _question_change_url(date_question)

    response = staff_client.post(
        url, _change_payload(staff_client.get(url), max="31/12/2010")
    )

    date_question.refresh_from_db()
    assert response.status_code == 200
    assert response.context["adminform"].form.errors
    assert date_question.max == ""


@pytest.mark.django_db
def test_the_admin_saves_a_valid_bound(staff_client, date_question) -> None:
    url = _question_change_url(date_question)

    staff_client.post(url, _change_payload(staff_client.get(url), max="2010-01-01"))

    date_question.refresh_from_db()
    assert date_question.max == "2010-01-01"


# ---------------------------------------------------------------------------
# The answers document on the FormProgress change page
# ---------------------------------------------------------------------------


def _change_page(client, progress) -> str:
    response = client.get(reverse(CHANGE_URL_NAME, args=[progress.pk]))
    assert response.status_code == 200
    return str(response.content.decode())


@pytest.mark.django_db
def test_the_change_page_walks_the_pages_in_form_order_and_marks_skips(
    staff_client,
) -> None:
    form = FormFactory()
    second = FormPageFactory(form=form, title="Zebra page", order=1)
    first = FormPageFactory(form=form, title="Aardvark page", order=0)
    FormQuestionFactory(form_page=first, question="Skipped query", order=0)
    FormQuestionFactory(form_page=second, question="Other query", order=0)
    progress = FormProgressFactory(form=form)

    body = _change_page(staff_client, progress)

    assert body.index("Aardvark page") < body.index("Zebra page")
    assert "Not answered" in body


@pytest.mark.django_db
def test_the_change_page_shows_options_dates_and_filenames_as_a_reader_sees_them(
    staff_client,
) -> None:
    form = FormFactory()
    page = FormPageFactory(form=form)
    choice = FormQuestionFactory(form_page=page, type="multiple_choice", order=0)
    option = QuestionOptionFactory(question=choice, text="Evenings only")
    date = FormQuestionFactory(form_page=page, type=QuestionType.DATE, order=1)
    file_question = FormQuestionFactory(form_page=page, type="file", order=2)
    progress = FormProgressFactory(form=form)
    QuestionAnswerFactory(form_progress=progress, question=choice).selected_options.add(
        option
    )
    QuestionAnswerFactory(
        form_progress=progress, question=date, text_answer="1987-03-14"
    )
    QuestionAnswerFileFactory(
        answer=QuestionAnswerFactory(form_progress=progress, question=file_question),
        original_filename="id-scan.png",
    )

    body = _change_page(staff_client, progress)

    assert "Evenings only" in body
    assert "March 14, 1987" in body
    assert "id-scan.png" in body


@pytest.mark.django_db
def test_the_final_group_heading_appears_only_with_an_off_page_answer(
    staff_client,
) -> None:
    form = FormFactory()
    FormQuestionFactory(form_page=FormPageFactory(form=form))
    progress = FormProgressFactory(form=form)
    assert FINAL_GROUP_TITLE not in _change_page(staff_client, progress)

    moved = FormQuestionFactory(form_page=FormPageFactory(form=FormFactory()))
    QuestionAnswerFactory(form_progress=progress, question=moved)

    assert FINAL_GROUP_TITLE in _change_page(staff_client, progress)


@pytest.mark.django_db
def test_the_change_page_is_read_only(staff_client) -> None:
    form = FormFactory()
    question = FormQuestionFactory(
        form_page=FormPageFactory(form=form), type=QuestionType.SHORT_TEXT
    )
    progress = FormProgressFactory(form=form)
    answer = QuestionAnswerFactory(
        form_progress=progress, question=question, text_answer="original"
    )
    url = reverse(CHANGE_URL_NAME, args=[progress.pk])

    response = staff_client.get(url)
    staff_client.post(url, {"text_answer": "changed"})

    answer.refresh_from_db()
    assert not response.context["adminform"].form.fields
    assert not response.context["inline_admin_formsets"]
    assert answer.text_answer == "original"


@pytest.mark.django_db
def test_the_add_page_offers_user_and_form(staff_client) -> None:
    response = staff_client.get(
        reverse("admin:freedom_ls_form_engine_formprogress_add")
    )

    fields = response.context["adminform"].form.fields
    assert {"user", "form"} <= set(fields)


@pytest.mark.django_db
def test_the_change_page_shows_furthest_page_reached(staff_client) -> None:
    progress = FormProgressFactory(furthest_page_reached=3)

    body = _change_page(staff_client, progress)

    assert "Furthest page reached" in body
