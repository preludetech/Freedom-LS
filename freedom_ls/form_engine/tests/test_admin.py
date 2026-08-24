"""Tests for FormProgressAdmin."""

from __future__ import annotations

import pytest

from django.urls import reverse

from freedom_ls.form_engine.factories import FormProgressFactory

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
