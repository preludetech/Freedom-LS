from __future__ import annotations

from datetime import date

import pytest

from freedom_ls.audit_log.models import REASON_LENGTH
from freedom_ls.deadlines.forms import PauseCourseForm, ResumeCourseForm


@pytest.mark.parametrize("form_class", [PauseCourseForm, ResumeCourseForm])
@pytest.mark.parametrize("reason", ["", "   "])
def test_a_blank_reason_is_refused(form_class, reason) -> None:
    form = form_class({"reason": reason})

    assert "reason" in form.errors


@pytest.mark.parametrize("form_class", [PauseCourseForm, ResumeCourseForm])
def test_a_reason_over_the_audit_cap_is_refused(form_class) -> None:
    form = form_class({"reason": "x" * (REASON_LENGTH + 1)})

    assert "reason" in form.errors


def test_the_planned_resume_date_is_optional() -> None:
    form = PauseCourseForm({"reason": "Leave"})

    assert form.is_valid()
    assert form.cleaned_data["planned_resume_on"] is None


def test_the_planned_resume_date_is_parsed() -> None:
    form = PauseCourseForm({"reason": "Leave", "planned_resume_on": "2030-01-05"})
    form.is_valid()

    assert form.cleaned_data["planned_resume_on"] == date(2030, 1, 5)
