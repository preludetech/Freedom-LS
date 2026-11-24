from __future__ import annotations

from freedom_ls.base.app_settings import AppSettings, Setting

DEFAULT_DECLARATION_TEXT = (
    "I declare that I am the person signed in to this account and that I am "
    "completing this quiz attempt myself, without help from anyone else. "
    "I understand that a false declaration may lead to my result being withdrawn."
)


class FormEngineConfig(AppSettings):
    FORM_DECLARATION_DEFAULT_TEXT: str

    declared_settings = {
        "FORM_DECLARATION_DEFAULT_TEXT": Setting(default=DEFAULT_DECLARATION_TEXT),
    }


config = FormEngineConfig()
