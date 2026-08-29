"""The form_engine admin: what it will not let an editor do."""

from __future__ import annotations

import re

import pytest

from django.contrib import admin
from django.urls import reverse

from freedom_ls.form_engine.admin import (
    FormAdmin,
    FormContentAdmin,
    FormPageAdmin,
    FormQuestionAdmin,
    QuestionOptionAdmin,
)
from freedom_ls.form_engine.factories import FormFactory, FormProgressFactory
from freedom_ls.form_engine.models import (
    Form,
    FormContent,
    FormPage,
    FormQuestion,
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
