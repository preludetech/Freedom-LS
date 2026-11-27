"""FormQuestionVersion: immutability, change detection and deletion."""

from __future__ import annotations

from typing import cast

import pytest
from pydantic import ValidationError

from django.db import IntegrityError, transaction
from django.db.models import ProtectedError

from freedom_ls.form_engine.factories import (
    FormQuestionFactory,
    QuestionOptionFactory,
)
from freedom_ls.form_engine.models import (
    FormQuestion,
    FormQuestionVersion,
    QuestionOption,
    QuestionVersionOption,
    delete_question_versions,
    save_question_version,
)

pytestmark = pytest.mark.django_db


def _options(question: FormQuestion) -> list[QuestionOption]:
    return list(question.options.all())


@pytest.fixture
def question(mock_site_context) -> FormQuestion:
    question = cast(
        FormQuestion,
        FormQuestionFactory(
            question="Pick one", explanation="Why", min="1", max="5", decimal_places=2
        ),
    )
    QuestionOptionFactory(question=question, text="A", value="a", order=0, correct=True)
    QuestionOptionFactory(
        question=question, text="B", value="b", order=1, correct=False
    )
    return question


@pytest.fixture
def saved(question) -> FormQuestionVersion:
    version = save_question_version(question, _options(question), "abc123").version
    assert version is not None
    return version


# Immutability


def test_saving_an_existing_version_raises(saved):
    with pytest.raises(ValueError, match="immutable"):
        saved.save()


def test_deleting_a_version_raises(saved):
    with pytest.raises(ValueError, match="immutable"):
        saved.delete()


@pytest.mark.parametrize("manager", ["objects", "unfiltered"])
def test_queryset_update_raises(saved, manager):
    with pytest.raises(ValueError, match="immutable"):
        getattr(FormQuestionVersion, manager).all().update(number=9)


@pytest.mark.parametrize("manager", ["objects", "unfiltered"])
def test_queryset_delete_raises(saved, manager):
    with pytest.raises(ValueError, match="immutable"):
        getattr(FormQuestionVersion, manager).all().delete()


@pytest.mark.parametrize("manager", ["objects", "unfiltered"])
def test_queryset_bulk_update_raises(saved, manager):
    with pytest.raises(ValueError, match="immutable"):
        getattr(FormQuestionVersion, manager).all().bulk_update([saved], ["number"])


def test_number_is_unique_per_question(saved):
    with pytest.raises(IntegrityError), transaction.atomic():
        FormQuestionVersion.objects.create(
            site_id=saved.site_id,
            question=saved.question,
            number=saved.number,
            question_text="x",
            type=saved.type,
        )


def test_option_rows_rejects_an_unknown_key(saved):
    bad = FormQuestionVersion(
        question=saved.question,
        number=2,
        question_text="x",
        type="multiple_choice",
        options=[
            {"id": "1", "text": "t", "value": "v", "order": 0, "correct": None, "x": 1}
        ],
    )

    with pytest.raises(ValidationError):
        bad.option_rows()


def test_option_rows_returns_validated_rows(saved):
    rows = saved.option_rows()

    assert [(r.text, r.correct) for r in rows] == [("A", True), ("B", False)]
    assert all(isinstance(r, QuestionVersionOption) for r in rows)


def test_version_site_is_its_questions_site(saved, question):
    assert saved.site_id == question.site_id


def test_deleting_a_question_with_a_version_is_refused(saved, question):
    with pytest.raises(ProtectedError), transaction.atomic():
        question.delete()


def test_delete_question_versions_empties_the_given_questions_only(saved):
    other = FormQuestionFactory()
    other_version = save_question_version(other, [], "").version
    assert other_version is not None

    delete_question_versions([saved.question])

    remaining = FormQuestionVersion.unfiltered.values_list("pk", flat=True)
    assert list(remaining) == [other_version.pk]


# Change detection


def test_first_save_makes_number_one_with_no_changed_fields(question):
    result = save_question_version(question, _options(question), "")

    assert result.version is not None
    assert (result.version.number, result.previous_number, result.changed) == (
        1,
        None,
        [],
    )


def test_unchanged_question_makes_no_version(saved, question):
    result = save_question_version(question, _options(question), "")

    assert result.version is None
    assert result.previous_number == 1


@pytest.mark.parametrize(
    ("field", "value", "name"),
    [
        ("question", "Another wording", "question"),
        ("type", "checkboxes", "type"),
        ("required", False, "required"),
        ("min", "2", "min"),
        ("max", "9", "max"),
        ("decimal_places", 3, "decimal_places"),
        ("explanation", "Because", "explanation"),
    ],
)
def test_changing_a_versioned_field_makes_a_version(
    saved, question, field, value, name
):
    setattr(question, field, value)
    question.save()

    result = save_question_version(question, _options(question), "")

    assert result.version is not None
    assert result.version.number == 2
    assert result.changed == [name]


def test_adding_an_option_makes_a_version(saved, question):
    QuestionOptionFactory(question=question, text="C", value="c", order=2)

    result = save_question_version(question, _options(question), "")

    assert result.changed == ["options"]


def test_removing_an_option_makes_a_version(saved, question):
    question.options.filter(text="B").delete()

    result = save_question_version(question, _options(question), "")

    assert result.changed == ["options"]


def test_reordering_options_makes_a_version(saved, question):
    option = question.options.get(text="A")
    option.order = 5
    option.save()

    result = save_question_version(question, _options(question), "")

    assert result.changed == ["options"]


def test_changing_an_options_correct_flag_makes_a_version(saved, question):
    option = question.options.get(text="B")
    option.correct = True
    option.save()

    result = save_question_version(question, _options(question), "")

    assert result.changed == ["options"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("slug", "new-slug"),
        ("tags", ["a"]),
        ("meta", {"k": "v"}),
        ("file_path", "other.md"),
        ("group", "g"),
        ("order", 42),
    ],
)
def test_changing_an_unversioned_field_makes_no_version(saved, question, field, value):
    setattr(question, field, value)
    question.save()

    result = save_question_version(question, _options(question), "")

    assert result.version is None


def test_locking_an_option_makes_no_version(saved, question):
    option = question.options.get(text="A")
    option.locked = True
    option.save()

    result = save_question_version(question, _options(question), "")

    assert result.version is None


def test_changing_the_page_makes_no_version(saved, question):
    from freedom_ls.form_engine.factories import FormPageFactory

    question.form_page = FormPageFactory(form=question.form_page.form)
    question.save()

    result = save_question_version(question, _options(question), "")

    assert result.version is None


def test_retiring_and_unretiring_makes_no_version(saved, question):
    from django.utils import timezone

    question.retired_at = timezone.now()
    question.save()
    retired = save_question_version(question, _options(question), "")
    question.retired_at = None
    question.save()

    unretired = save_question_version(question, _options(question), "")

    assert (retired.version, unretired.version) == (None, None)


def test_a_revert_makes_a_new_number(saved, question):
    question.question = "Changed"
    question.save()
    save_question_version(question, _options(question), "")
    question.question = "Pick one"
    question.save()

    result = save_question_version(question, _options(question), "")

    assert result.version is not None
    assert result.version.number == 3
