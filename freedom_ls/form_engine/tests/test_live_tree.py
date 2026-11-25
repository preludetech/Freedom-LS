"""The pages, children and options of a form that a new sitting may be served."""

from __future__ import annotations

from typing import cast

import pytest

from freedom_ls.form_engine.factories import (
    FormContentFactory,
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
    QuestionOptionFactory,
)
from freedom_ls.form_engine.live_tree import live_children, live_options, live_pages
from freedom_ls.form_engine.models import (
    FormContent,
    FormPage,
    FormQuestion,
    QuestionOption,
)
from freedom_ls.tests.retire import retire

pytestmark = pytest.mark.django_db


def test_live_pages_leaves_out_a_retired_page_and_keeps_the_order(
    mock_site_context: object,
) -> None:
    form = FormFactory()
    first = FormPageFactory(form=form, order=0)
    retire(cast("FormPage", FormPageFactory(form=form, order=1)))
    last = FormPageFactory(form=form, order=2)

    assert live_pages(form) == [first, last]


def test_live_children_leaves_out_retired_content_and_questions_in_page_order(
    mock_site_context: object,
) -> None:
    page = FormPageFactory()
    content = FormContentFactory(form_page=page, order=0)
    retire(cast("FormQuestion", FormQuestionFactory(form_page=page, order=1)))
    question = FormQuestionFactory(form_page=page, order=2)
    retire(cast("FormContent", FormContentFactory(form_page=page, order=3)))

    assert live_children(page) == [content, question]


def test_live_options_leaves_out_a_retired_option(mock_site_context: object) -> None:
    question = FormQuestionFactory()
    kept = QuestionOptionFactory(question=question, order=0)
    retire(cast("QuestionOption", QuestionOptionFactory(question=question, order=1)))

    assert live_options(question) == [kept]
