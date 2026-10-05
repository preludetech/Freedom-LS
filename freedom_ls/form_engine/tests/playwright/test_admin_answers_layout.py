"""The admin answers document keeps the paragraph breaks a long answer was typed with.

Whether a newline renders as a line break depends on the CSS the admin actually
loads, which only a real browser can settle.
"""

from __future__ import annotations

import pytest
from allauth.account.models import EmailAddress
from playwright.sync_api import Page, expect

from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormProgressFactory,
    FormQuestionFactory,
    QuestionAnswerFactory,
)
from freedom_ls.tests.playwright_fixtures import _LOGGED_IN_PASSWORD, _login_via_ui

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]

_THREE_PARAGRAPHS = (
    "First paragraph of the answer.\n\n"
    "Second paragraph of the answer.\n\n"
    "Third paragraph of the answer."
)


@pytest.fixture
def admin_user(db, live_server_site, mock_site_context) -> User:
    """A fresh, email-verified superuser."""
    user: User = UserFactory(superuser=True, password=_LOGGED_IN_PASSWORD)
    EmailAddress.objects.get_or_create(
        user=user,
        email=user.email,
        defaults={"verified": True, "primary": True},
    )
    return user


def test_a_long_answer_keeps_its_paragraph_breaks_in_the_admin(
    page: Page, live_server, admin_user: User
) -> None:
    """The answer's newlines used to collapse into one run-together block."""
    form = FormFactory()
    question = FormQuestionFactory(
        form_page=FormPageFactory(form=form), type="text_area", order=0
    )
    progress = FormProgressFactory(form=form)
    QuestionAnswerFactory(
        form_progress=progress, question=question, text_answer=_THREE_PARAGRAPHS
    )
    _login_via_ui(page, live_server, str(admin_user.email), _LOGGED_IN_PASSWORD)

    page.goto(
        live_server.url
        + reverse(
            "admin:freedom_ls_form_engine_formprogress_change", args=[progress.pk]
        )
    )

    answer = page.get_by_text("First paragraph of the answer.")
    expect(answer).to_be_visible()
    # Three paragraphs separated by blank lines lay out as five lines.
    line_height = answer.evaluate("el => parseFloat(getComputedStyle(el).lineHeight)")
    height = answer.evaluate("el => el.getBoundingClientRect().height")
    assert height >= 4.5 * line_height
