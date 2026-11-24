"""The shipped declaration demo course validates and loads two quizzes that require a declaration.

Marked `fls_internal`: it reads `demo_content/`, which only this repo ships.
"""

from __future__ import annotations

import pytest

from django.conf import settings
from django.contrib.sites.models import Site

from freedom_ls.content_engine.validate import validate
from freedom_ls.form_engine.config import config as form_engine_config
from freedom_ls.form_engine.models import Form

pytestmark = pytest.mark.fls_internal

OWN_TEXT_TITLE = "Quiz with its own declaration"
DEFAULT_TEXT_TITLE = "Quiz with the default declaration"


def test_the_demo_courses_validate() -> None:
    validate(settings.BASE_DIR / "demo_content")


@pytest.mark.django_db
def test_both_demo_quizzes_require_a_declaration(
    site: Site,
    loaded_demo_content: Site,
    mock_site_context: object,
) -> None:
    forms = Form.objects.filter(title__in=[OWN_TEXT_TITLE, DEFAULT_TEXT_TITLE])

    assert sorted(forms.values_list("requires_declaration", flat=True)) == [True, True]


@pytest.mark.django_db
def test_the_first_demo_quiz_has_its_own_two_paragraph_declaration_text(
    site: Site,
    loaded_demo_content: Site,
    mock_site_context: object,
) -> None:
    form = Form.objects.get(title=OWN_TEXT_TITLE, site=site)

    assert (
        form.effective_declaration_text() == form.declaration_text,
        len(form.declaration_text.split("\n\n")),
    ) == (True, 2)


@pytest.mark.django_db
def test_the_second_demo_quiz_uses_the_default_declaration_text(
    site: Site,
    loaded_demo_content: Site,
    mock_site_context: object,
) -> None:
    form = Form.objects.get(title=DEFAULT_TEXT_TITLE, site=site)

    assert (
        form.declaration_text,
        form.effective_declaration_text(),
    ) == ("", form_engine_config.FORM_DECLARATION_DEFAULT_TEXT)
