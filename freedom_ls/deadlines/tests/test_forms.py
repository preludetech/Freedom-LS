from __future__ import annotations

from datetime import date

import pytest

from django.http import QueryDict

from freedom_ls.audit_log.models import REASON_LENGTH
from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.content_engine.tests.helpers import collection_item_for
from freedom_ls.deadlines.forms import (
    ExtendDeadlineForm,
    PauseCourseForm,
    ResumeCourseForm,
)
from freedom_ls.deadlines.models import MAX_EXTENSION_DAYS
from freedom_ls.learner_progress.factories import CourseProgressFactory


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


def _extend_form(record, **data: str) -> ExtendDeadlineForm:
    post = QueryDict(mutable=True)
    post.update({"reason": "Ill", **data})
    return ExtendDeadlineForm(record, post)


@pytest.fixture
def record_with_item(db, mock_site_context):
    course = CourseFactory()
    topic = TopicFactory()
    course.items.create(child=topic, order=0)
    return CourseProgressFactory(course=course), collection_item_for(course, topic)


def test_an_item_extension_by_days_is_valid(record_with_item) -> None:
    record, item = record_with_item

    form = _extend_form(
        record, target_kind="collection_item", collection_item=str(item.pk), days="3"
    )

    assert form.is_valid(), form.errors
    assert form.cleaned_data["collection_item"] == item
    assert form.cleaned_data["days"] == 3


def test_the_item_picker_offers_only_the_records_course(record_with_item) -> None:
    record, item = record_with_item
    other_course = CourseFactory()
    other_topic = TopicFactory()
    other_course.items.create(child=other_topic, order=0)
    foreign = collection_item_for(other_course, other_topic)

    form = _extend_form(record)

    assert list(form.fields["collection_item"].queryset) == [item]
    assert foreign not in form.fields["collection_item"].queryset


@pytest.mark.parametrize(
    ("data", "field"),
    [
        pytest.param({"days": "2", "requested_date": "2030-01-05"}, None, id="both"),
        pytest.param({}, None, id="neither"),
        pytest.param({"days": "0"}, "days", id="zero-days"),
        pytest.param({"days": str(MAX_EXTENSION_DAYS + 1)}, "days", id="too-many-days"),
        pytest.param({"days": "2", "reason": ""}, "reason", id="blank-reason"),
        pytest.param(
            {"days": "2", "target_kind": "collection_item"},
            "collection_item",
            id="item-missing",
        ),
    ],
)
def test_an_invalid_extension_is_refused(record_with_item, data, field) -> None:
    record, _ = record_with_item
    data = {"target_kind": "time_limit", **data}

    form = _extend_form(record, **data)

    assert not form.is_valid()
    assert (field in form.errors) if field else form.non_field_errors()


def test_a_date_for_the_whole_course_is_refused(record_with_item) -> None:
    record, _ = record_with_item

    form = _extend_form(record, target_kind="course", requested_date="2030-01-05")

    assert "requested_date" in form.errors


def test_an_item_with_a_non_item_target_is_refused(record_with_item) -> None:
    record, item = record_with_item

    form = _extend_form(
        record, target_kind="time_limit", collection_item=str(item.pk), days="2"
    )

    assert "collection_item" in form.errors
