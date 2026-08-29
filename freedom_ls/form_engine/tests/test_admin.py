"""Tests for FormProgressAdmin."""

from __future__ import annotations

import pytest

from django.contrib import admin
from django.urls import reverse

from freedom_ls.form_engine.admin import (
    FormAdmin,
    FormContentAdmin,
    FormContentInline,
    FormPageAdmin,
    FormPageInline,
    FormQuestionAdmin,
    FormQuestionInline,
    QuestionOptionAdmin,
    QuestionOptionInline,
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


class TestDeletePermissionAlwaysFalse:
    def test_form_admin(self) -> None:
        assert FormAdmin(Form, admin.site).has_delete_permission(request=None) is False

    def test_form_page_admin(self) -> None:
        assert (
            FormPageAdmin(FormPage, admin.site).has_delete_permission(request=None)
            is False
        )

    def test_form_content_admin(self) -> None:
        assert (
            FormContentAdmin(FormContent, admin.site).has_delete_permission(
                request=None
            )
            is False
        )

    def test_form_question_admin(self) -> None:
        assert (
            FormQuestionAdmin(FormQuestion, admin.site).has_delete_permission(
                request=None
            )
            is False
        )

    def test_question_option_admin(self) -> None:
        assert (
            QuestionOptionAdmin(QuestionOption, admin.site).has_delete_permission(
                request=None
            )
            is False
        )


class TestInlinesCannotDelete:
    def test_form_page_inline(self) -> None:
        assert FormPageInline.can_delete is False

    def test_form_content_inline(self) -> None:
        assert FormContentInline.can_delete is False

    def test_form_question_inline(self) -> None:
        assert FormQuestionInline.can_delete is False

    def test_question_option_inline(self) -> None:
        assert QuestionOptionInline.can_delete is False


FORM_CHANGELIST_URL_NAME = "admin:freedom_ls_form_engine_form_changelist"


@pytest.mark.django_db
def test_form_changelist_filters_by_tag(staff_client):
    """FormAdmin filters on the same ArrayField-aware tag filter."""
    tagged = FormFactory(title="Tagged quiz", tags=["python"])
    FormFactory(title="Other quiz", tags=["django"])

    response = staff_client.get(reverse(FORM_CHANGELIST_URL_NAME), {"tag": "python"})

    assert [form.pk for form in response.context["cl"].result_list] == [tagged.pk]
