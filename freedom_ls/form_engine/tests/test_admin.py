"""The form_engine admin: who may open, add to and delete from it."""

from __future__ import annotations

import pytest

from django.contrib import admin
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import Client, RequestFactory
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.form_engine.admin import (
    QuestionAnswerAdmin,
    applicant_label,
)
from freedom_ls.form_engine.enums import QuestionType
from freedom_ls.form_engine.factories import (
    FormDeclarationFactory,
    FormFactory,
    FormPageFactory,
    FormProgressFactory,
    FormQuestionFactory,
    QuestionAnswerFactory,
    QuestionAnswerFileFactory,
    QuestionOptionFactory,
)
from freedom_ls.form_engine.models import (
    QuestionAnswer,
)
from freedom_ls.form_engine.queries import FINAL_GROUP_TITLE
from freedom_ls.tests.retire import retired

CHANGE_URL_NAME = "admin:freedom_ls_form_engine_formprogress_change"


@pytest.mark.django_db
class TestFormProgressChangelist:
    """The changelist that answers "who has finished this form, and when"."""

    CHANGELIST_URL_NAME = "admin:freedom_ls_form_engine_formprogress_changelist"

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


def _answer_url(model_name: str, view: str, *args: object) -> str:
    return reverse(f"admin:freedom_ls_form_engine_{model_name}_{view}", args=args)


@pytest.mark.django_db
@pytest.mark.parametrize("model_name", ANSWER_MODELS)
def test_the_answer_changelist_opens_for_a_superuser_and_lists_the_row(
    staff_client: Client, model_name: str
) -> None:
    row = ANSWER_FACTORIES[model_name]()

    response = staff_client.get(_answer_url(model_name, "changelist"))

    assert response.status_code == 200
    assert [r.pk for r in response.context["cl"].result_list] == [row.pk]


@pytest.mark.django_db
@pytest.mark.parametrize("model_name", ANSWER_MODELS)
def test_the_answer_change_page_has_no_save_button(
    staff_client: Client, model_name: str
) -> None:
    row = ANSWER_FACTORIES[model_name]()

    response = staff_client.get(_answer_url(model_name, "change", row.pk))

    assert response.status_code == 200
    assert 'name="_save"' not in response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize("model_name", ANSWER_MODELS)
def test_a_superuser_cannot_open_the_answer_add_page(
    staff_client: Client, model_name: str
) -> None:
    response = staff_client.get(_answer_url(model_name, "add"))

    assert response.status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize("model_name", ANSWER_MODELS)
def test_a_superuser_cannot_change_an_answer_row(
    staff_client: Client, model_name: str
) -> None:
    row = ANSWER_FACTORIES[model_name]()
    before = type(row)._base_manager.values().get(pk=row.pk)

    response = staff_client.post(
        _answer_url(model_name, "change", row.pk), {"text_answer": "changed"}
    )

    assert response.status_code == 403
    assert type(row)._base_manager.values().get(pk=row.pk) == before


@pytest.mark.django_db
@pytest.mark.parametrize("model_name", ANSWER_MODELS)
def test_a_superuser_cannot_delete_an_answer_row(
    staff_client: Client, model_name: str
) -> None:
    """Django's delete view consults only has_delete_permission, so not even a
    superuser may destroy an applicant's ID scan."""
    row = ANSWER_FACTORIES[model_name]()

    response = staff_client.post(
        _answer_url(model_name, "delete", row.pk), {"post": "yes"}
    )

    assert response.status_code == 403
    assert type(row)._base_manager.filter(pk=row.pk).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("model_name", ANSWER_MODELS)
def test_the_answer_admin_offers_no_delete_selected_action(
    staff_client: Client, rf: RequestFactory, model_name: str
) -> None:
    request = rf.get("/")
    request.user = UserFactory(superuser=True)
    model = ANSWER_FACTORIES[model_name]._meta.model

    actions = admin.site.get_model_admin(model).get_actions(request)

    assert "delete_selected" not in actions


@pytest.mark.django_db
@pytest.mark.parametrize("model_name", ANSWER_MODELS)
def test_posting_delete_selected_to_the_changelist_leaves_the_row(
    staff_client: Client, model_name: str
) -> None:
    row = ANSWER_FACTORIES[model_name]()

    response = staff_client.post(
        _answer_url(model_name, "changelist"),
        {"action": "delete_selected", "_selected_action": [row.pk], "index": 0},
    )

    assert response.status_code == 200
    assert type(row)._base_manager.filter(pk=row.pk).exists()


@pytest.mark.django_db
def test_the_form_progress_changelist_filters_to_one_forms_sittings(
    staff_client: Client,
) -> None:
    wanted = FormProgressFactory()
    FormProgressFactory()

    response = staff_client.get(
        _answer_url("formprogress", "changelist"), {"form__id__exact": wanted.form.pk}
    )

    assert response.status_code == 200
    assert [r.pk for r in response.context["cl"].result_list] == [wanted.pk]


@pytest.mark.django_db
def test_the_form_progress_change_page_renders_each_questions_text(
    staff_client: Client,
) -> None:
    form = FormFactory()
    page = FormPageFactory(form=form)
    FormQuestionFactory(form_page=page, question="Alpha question text", order=0)
    FormQuestionFactory(form_page=page, question="Beta question text", order=1)
    progress = FormProgressFactory(form=form)

    body = _change_page(staff_client, progress)

    assert "Alpha question text" in body
    assert "Beta question text" in body


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


@pytest.mark.django_db
def test_the_change_page_marks_a_retired_question_and_a_chosen_retired_option(
    staff_client: Client,
) -> None:
    form = FormFactory()
    page = FormPageFactory(form=form)
    question = retired(
        FormQuestionFactory(form_page=page, type="multiple_choice", order=0)
    )
    option = retired(QuestionOptionFactory(question=question, text="Gone option"))
    progress = FormProgressFactory(form=form)
    QuestionAnswerFactory(
        form_progress=progress, question=question
    ).selected_options.add(option)

    body = _change_page(staff_client, progress)

    assert body.count("Retired") == 2
    assert "Gone option" in body


@pytest.mark.django_db
def test_the_change_page_marks_nothing_retired_for_live_content(
    staff_client: Client,
) -> None:
    form = FormFactory()
    page = FormPageFactory(form=form)
    question = FormQuestionFactory(form_page=page, type="multiple_choice", order=0)
    option = QuestionOptionFactory(question=question)
    progress = FormProgressFactory(form=form)
    QuestionAnswerFactory(
        form_progress=progress, question=question
    ).selected_options.add(option)

    assert "Retired" not in _change_page(staff_client, progress)


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
def test_the_change_page_shows_the_furthest_page(staff_client) -> None:
    form = FormFactory()
    page = FormPageFactory(form=form, title="Medical history")
    progress = FormProgressFactory(form=form, furthest_page=page)

    body = _change_page(staff_client, progress)

    assert "Medical history" in body


def _progress_with_file_answer(filename: str = "id-scan.png"):
    form = FormFactory()
    page = FormPageFactory(form=form)
    question = FormQuestionFactory(form_page=page, type="file", order=0)
    progress = FormProgressFactory(form=form)
    answer_file = QuestionAnswerFileFactory(
        answer=QuestionAnswerFactory(form_progress=progress, question=question),
        original_filename=filename,
    )
    return progress, answer_file


@pytest.mark.django_db
def test_a_superuser_sees_the_filename_and_a_download_link(staff_client) -> None:
    progress, answer_file = _progress_with_file_answer()

    body = _change_page(staff_client, progress)

    assert "id-scan.png" in body
    assert _admin_download_url(answer_file) in body


@pytest.mark.django_db
def test_a_reader_without_file_permission_sees_the_filename_but_no_link(
    mock_site_context, logged_in_client
) -> None:
    viewer = UserFactory(is_staff=True, is_superuser=False)
    viewer.user_permissions.set(
        Permission.objects.filter(
            content_type__app_label="freedom_ls_form_engine",
            codename="view_formprogress",
        )
    )
    progress, answer_file = _progress_with_file_answer()

    body = _change_page(logged_in_client(viewer), progress)

    assert "id-scan.png" in body
    assert _admin_download_url(answer_file) not in body


@pytest.mark.django_db
def test_the_change_page_of_a_sitting_with_no_application_has_no_summary_rows(
    staff_client,
) -> None:
    progress = FormProgressFactory()

    response = staff_client.get(reverse(CHANGE_URL_NAME, args=[progress.pk]))

    assert response.status_code == 200
    assert "summary_rows" not in response.context


@pytest.mark.django_db
def test_applicant_label_for_a_sitting_with_a_user_is_the_user(mock_site_context):
    progress = FormProgressFactory(user=UserFactory(email="sitter@example.com"))

    assert applicant_label(progress) == str(progress.user)


@pytest.mark.django_db
def test_applicant_label_for_a_user_less_sitting_with_no_application(
    mock_site_context,
):
    progress = FormProgressFactory(user=None)

    assert applicant_label(progress) == "Unverified"


@pytest.mark.django_db
def test_the_change_page_shows_the_declaration_read_only(staff_client: Client) -> None:
    progress = FormProgressFactory()
    FormDeclarationFactory(
        form_progress=progress,
        declaration_text="I sat this quiz alone.",
        typed_name="Ada Lovelace",
        ip_address="203.0.113.7",
    )

    response = staff_client.get(reverse(CHANGE_URL_NAME, args=[progress.pk]))

    body = response.content.decode()
    assert "I sat this quiz alone." in body
    assert "Ada Lovelace" in body
    assert "203.0.113.7" in body
    assert "Signed at" in body
    assert "form-declaration-0-DELETE" not in body
    assert not response.context["inline_admin_formsets"][0].has_add_permission
