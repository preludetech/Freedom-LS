from __future__ import annotations

from django.test import override_settings

from freedom_ls.form_engine.config import DEFAULT_DECLARATION_TEXT, config


def test_the_default_declaration_text_is_the_shipped_wording() -> None:
    assert config.FORM_DECLARATION_DEFAULT_TEXT == DEFAULT_DECLARATION_TEXT
    assert DEFAULT_DECLARATION_TEXT == (
        "I declare that I am the person signed in to this account and that I am "
        "completing this quiz attempt myself, without help from anyone else. "
        "I understand that a false declaration may lead to my result being withdrawn."
    )


def test_a_project_setting_replaces_the_default_declaration_text() -> None:
    with override_settings(FORM_DECLARATION_DEFAULT_TEXT="Project wording."):
        assert config.FORM_DECLARATION_DEFAULT_TEXT == "Project wording."
