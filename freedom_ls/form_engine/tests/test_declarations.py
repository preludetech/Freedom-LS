from __future__ import annotations

import pytest

from django.contrib.auth.models import AnonymousUser

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.form_engine.declarations import (
    declaration_text_hash,
    form_requires_declaration,
    sitting_needs_declaration,
)
from freedom_ls.form_engine.factories import (
    FormDeclarationFactory,
    FormFactory,
    FormProgressFactory,
)
from freedom_ls.form_engine.models import FormStrategy


@pytest.mark.django_db
def test_a_quiz_with_the_flag_requires_a_declaration_of_a_signed_in_user(
    mock_site_context: object,
) -> None:
    form = FormFactory(strategy=FormStrategy.QUIZ, requires_declaration=True)

    assert form_requires_declaration(form, UserFactory()) is True


@pytest.mark.django_db
def test_an_anonymous_user_is_not_asked_for_a_declaration(
    mock_site_context: object,
) -> None:
    form = FormFactory(strategy=FormStrategy.QUIZ, requires_declaration=True)

    assert form_requires_declaration(form, AnonymousUser()) is False


@pytest.mark.django_db
def test_a_quiz_without_the_flag_requires_no_declaration(
    mock_site_context: object,
) -> None:
    form = FormFactory(strategy=FormStrategy.QUIZ, requires_declaration=False)

    assert form_requires_declaration(form, UserFactory()) is False


@pytest.mark.django_db
def test_a_form_that_is_not_a_quiz_requires_no_declaration(
    mock_site_context: object,
) -> None:
    form = FormFactory(
        strategy=FormStrategy.CATEGORY_VALUE_SUM, requires_declaration=True
    )

    assert form_requires_declaration(form, UserFactory()) is False


@pytest.mark.django_db
def test_an_unsigned_sitting_of_a_declaration_quiz_needs_its_declaration(
    mock_site_context: object,
) -> None:
    form = FormFactory(strategy=FormStrategy.QUIZ, requires_declaration=True)
    sitting = FormProgressFactory(form=form)

    assert sitting_needs_declaration(sitting) is True


@pytest.mark.django_db
def test_a_signed_sitting_needs_no_declaration(mock_site_context: object) -> None:
    form = FormFactory(strategy=FormStrategy.QUIZ, requires_declaration=True)
    sitting = FormProgressFactory(form=form)
    FormDeclarationFactory(form_progress=sitting)

    assert sitting_needs_declaration(sitting) is False


@pytest.mark.django_db
def test_an_anonymous_sitting_needs_no_declaration(mock_site_context: object) -> None:
    form = FormFactory(strategy=FormStrategy.QUIZ, requires_declaration=True)
    sitting = FormProgressFactory(form=form, user=None)

    assert sitting_needs_declaration(sitting) is False


def test_the_text_hash_differs_when_one_character_differs() -> None:
    assert declaration_text_hash("I declare.") != declaration_text_hash("I declare!")
    assert declaration_text_hash("I declare.") == declaration_text_hash("I declare.")
