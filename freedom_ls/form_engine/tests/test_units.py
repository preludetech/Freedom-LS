"""How a page's children split into the units that shuffle and draw as one."""

from __future__ import annotations

import pytest

from freedom_ls.content_base.schema import ContentType
from freedom_ls.form_engine import schema
from freedom_ls.form_engine.factories import (
    FormContentFactory,
    FormPageFactory,
    FormQuestionFactory,
)
from freedom_ls.form_engine.models import FormQuestion
from freedom_ls.form_engine.units import shuffle_units, unit_question_counts


def _schema_children(groups: list[str | None]) -> list[schema.FormContent]:
    return [
        schema.FormContent(
            content_type=ContentType.FORM_CONTENT,
            file_path=f"c{i}.md",
            content=f"c{i}",
            group=g,
            meta=None,
            uuid=None,
            when=None,
        )
        for i, g in enumerate(groups)
    ]


@pytest.mark.parametrize(
    ("groups", "expected_sizes"),
    [
        ([None, None, None], [1, 1, 1]),
        ([None, "a", "a", None], [1, 2, 1]),
        (["a", "a", "b", "b", "b"], [2, 3]),
        (["a", None, "a"], [1, 1, 1]),
    ],
)
def test_shuffle_units_on_schema_children_groups_runs_and_leaves_the_rest_alone(
    groups: list[str | None], expected_sizes: list[int]
) -> None:
    children = _schema_children(groups)

    units = shuffle_units(children)

    assert [len(u) for u in units] == expected_sizes
    assert [c for unit in units for c in unit] == children


@pytest.mark.django_db
def test_shuffle_units_on_model_rows_treats_a_blank_group_as_ungrouped(
    mock_site_context: object,
) -> None:
    page = FormPageFactory()
    plain = FormContentFactory(form_page=page, order=0)
    first = FormQuestionFactory(form_page=page, order=1, group="g")
    second = FormContentFactory(form_page=page, order=2, group="g")
    last = FormQuestionFactory(form_page=page, order=3)

    units = shuffle_units(page.children())

    assert units == [[plain], [first, second], [last]]


@pytest.mark.django_db
def test_unit_question_counts_counts_only_the_questions_in_each_unit(
    mock_site_context: object,
) -> None:
    page = FormPageFactory()
    FormContentFactory(form_page=page, order=0, group="g")
    FormQuestionFactory(form_page=page, order=1, group="g")
    FormQuestionFactory(form_page=page, order=2, group="g")
    FormContentFactory(form_page=page, order=3)
    FormQuestionFactory(form_page=page, order=4)

    counts = unit_question_counts(
        shuffle_units(page.children()), lambda c: isinstance(c, FormQuestion)
    )

    assert counts == [2, 0, 1]
