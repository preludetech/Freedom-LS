from __future__ import annotations

from django.http import QueryDict

from freedom_ls.form_engine.declarations import declaration_text_hash
from freedom_ls.learner_interface.forms import FormDeclarationForm

TEXT = "I did this myself."


def _form(**overrides: str) -> FormDeclarationForm:
    data = {
        "agreed": "on",
        "typed_name": "Thandi Nkosi",
        "text_hash": declaration_text_hash(TEXT),
        **overrides,
    }
    query = QueryDict(mutable=True)
    for key, value in data.items():
        if value != "":
            query[key] = value
    return FormDeclarationForm(query, declaration_text=TEXT)


def test_a_ticked_box_a_name_and_the_current_hash_are_valid() -> None:
    assert _form().is_valid() is True


def test_the_typed_name_keeps_its_leading_and_trailing_spaces() -> None:
    form = _form(typed_name="  Thandi Nkosi ")

    assert form.is_valid()
    assert form.cleaned_data["typed_name"] == "  Thandi Nkosi "


def test_a_whitespace_only_name_is_invalid() -> None:
    form = _form(typed_name="   ")

    assert form.is_valid() is False
    assert "typed_name" in form.errors


def test_an_unticked_box_is_invalid() -> None:
    form = _form(agreed="")

    assert form.is_valid() is False
    assert "agreed" in form.errors


def test_a_wrong_hash_is_invalid_and_reports_the_declaration_changed() -> None:
    form = _form(text_hash="0" * 64)

    assert form.is_valid() is False
    assert form.declaration_changed() is True


def test_an_unrelated_error_does_not_report_the_declaration_changed() -> None:
    form = _form(agreed="")

    assert form.is_valid() is False
    assert form.declaration_changed() is False


def test_an_unbound_form_carries_the_current_hash_as_its_initial_value() -> None:
    form = FormDeclarationForm(declaration_text=TEXT)

    assert form["text_hash"].value() == declaration_text_hash(TEXT)
