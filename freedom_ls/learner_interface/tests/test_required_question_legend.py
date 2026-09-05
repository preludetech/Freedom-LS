"""A question legend has to hold the number, the question and the required
asterisk on the right lines: the number beside the question's first line, the
asterisk glued to its last word, and a two-paragraph question rendered as two
paragraphs rather than run together into one.
"""

from __future__ import annotations

import re

import pytest

from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
)

from .conftest import course_with_form, register_user_for_course


def _legend_html(client, question_text: str, *, required: bool = True) -> str:
    """Render a one-question runner page and return just its <legend> markup."""
    form = FormFactory(title="Legend form")
    page = FormPageFactory(form=form, title="Page 1", order=0)
    FormQuestionFactory(
        form_page=page,
        question=question_text,
        type="long_text",
        required=required,
        order=0,
    )

    user = UserFactory()
    course = course_with_form(form)
    register_user_for_course(course, user)
    client.force_login(user)
    client.get(
        reverse(
            "learner_interface:form_start",
            kwargs={"course_slug": course.slug, "index": 1},
        )
    )
    response = client.get(
        reverse(
            "learner_interface:form_fill_page",
            kwargs={"course_slug": course.slug, "index": 1, "page_number": 1},
        )
    )
    assert response.status_code == 200

    legend = re.search(r"<legend\b.*?</legend>", response.content.decode(), re.DOTALL)
    assert legend is not None, "the runner page rendered no legend"
    return legend.group(0)


@pytest.mark.django_db
def test_a_two_paragraph_question_keeps_its_paragraphs_apart(mock_site_context, client):
    """Inlining every paragraph ran them together with no separator between them."""
    legend = _legend_html(client, "First paragraph.\n\nSecond paragraph.")

    assert legend.count("<p>") == 2
    # Only the last paragraph is inlined, so the first keeps its own line.
    assert "[&>p:last-of-type]:inline" in legend
    assert "[&>p]:inline" not in legend


@pytest.mark.django_db
def test_the_required_asterisk_is_the_last_thing_in_the_legend(
    mock_site_context, client
):
    """The asterisk trails the question's final paragraph, so it cannot wrap alone."""
    legend = _legend_html(client, "First paragraph.\n\nSecond paragraph.")

    tail = legend[legend.rindex("</p>") :]
    assert "&nbsp;" in tail
    assert 'data-testid="required-indicator-1"' in tail
    assert "(required)" in tail


@pytest.mark.django_db
def test_a_question_that_is_not_required_carries_no_asterisk(mock_site_context, client):
    legend = _legend_html(client, "Just the one paragraph.", required=False)

    assert "required-indicator" not in legend
    assert "(required)" not in legend
