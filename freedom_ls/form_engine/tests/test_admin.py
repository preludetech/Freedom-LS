"""The form_engine admin: what it will not let an editor do."""

from __future__ import annotations

import re

import pytest

from django.contrib import admin
from django.contrib.auth.models import Permission
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.form_engine.admin import (
    FormAdmin,
    FormContentAdmin,
    FormPageAdmin,
    FormQuestionAdmin,
    QuestionOptionAdmin,
)
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormProgressFactory,
    QuestionAnswerFactory,
    QuestionAnswerFileFactory,
)
from freedom_ls.form_engine.models import (
    Form,
    FormContent,
    FormPage,
    FormQuestion,
    FormStrategy,
    QuestionOption,
)

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
# Answer data is restricted to superusers
# ---------------------------------------------------------------------------


@pytest.fixture
def editor_client(mock_site_context, logged_in_client):
    """The admin as staff who are not a superuser.

    Granted every model permission there is, so what the tests below measure is
    the superuser gate itself rather than an editor who simply has no rights.
    """
    editor = UserFactory(is_staff=True, is_superuser=False)
    editor.user_permissions.set(Permission.objects.all())
    return logged_in_client(editor)


ANSWER_CHANGELISTS = [
    "admin:freedom_ls_form_engine_questionanswer_changelist",
    "admin:freedom_ls_form_engine_formprogress_changelist",
    "admin:freedom_ls_form_engine_questionanswerfile_changelist",
]


@pytest.mark.django_db
@pytest.mark.parametrize("url_name", ANSWER_CHANGELISTS)
def test_an_editor_cannot_reach_answer_data(editor_client, url_name):
    """A sitting and its answers are an applicant's own words and documents.
    Content editing rights are not rights over those.
    """
    response = editor_client.get(reverse(url_name))

    assert response.status_code == 403


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
def test_an_editor_cannot_add_answer_data(editor_client, model_name):
    """Django's add view consults only has_add_permission, so the view and
    change gates alone would leave an editor free to fabricate an answer."""
    response = editor_client.get(
        reverse(f"admin:freedom_ls_form_engine_{model_name}_add")
    )

    assert response.status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize("model_name", ANSWER_MODELS)
def test_an_editor_cannot_delete_answer_data(editor_client, model_name):
    """Django's delete view consults only has_delete_permission, so the view and
    change gates alone would leave an editor free to destroy an applicant's ID
    scan."""
    row = ANSWER_FACTORIES[model_name]()

    response = editor_client.post(
        reverse(f"admin:freedom_ls_form_engine_{model_name}_delete", args=[row.pk]),
        {"post": "yes"},
    )

    assert response.status_code == 403
    assert type(row)._base_manager.filter(pk=row.pk).exists()


@pytest.mark.django_db
def test_the_admin_index_lists_no_answer_data_for_an_editor(editor_client):
    """A model with any one of add, change, delete or view still gets an index
    entry, so all four have to be shut for the listing to go."""
    response = editor_client.get(reverse("admin:index"))

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
# The reviewer's download route
# ---------------------------------------------------------------------------


def _admin_download_url(answer_file) -> str:
    return reverse(
        "admin:freedom_ls_form_engine_questionanswerfile_download",
        args=[answer_file.pk],
    )


@pytest.mark.django_db
def test_an_editor_cannot_download_an_answer_file(mock_site_context, editor_client):
    answer_file = QuestionAnswerFileFactory()

    response = editor_client.get(_admin_download_url(answer_file))

    assert response.status_code == 403


@pytest.mark.django_db
def test_an_answer_file_is_served_to_a_reviewer(mock_site_context, staff_client):
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
