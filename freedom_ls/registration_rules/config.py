from __future__ import annotations

from freedom_ls.base.app_settings import AppSettings, Setting


class RegistrationRulesSettings(AppSettings):
    # Kind key to the dotted path of the class that decides who a rule matches.
    REGISTRATION_RULE_KINDS: dict[str, str]
    # Learners per transaction when a whole rule is evaluated.
    REGISTRATION_RULE_BATCH_SIZE: int

    declared_settings = {
        "REGISTRATION_RULE_KINDS": Setting(
            default={
                "attribute": "freedom_ls.registration_rules.kinds.AttributeRuleKind"
            }
        ),
        "REGISTRATION_RULE_BATCH_SIZE": Setting(default=500),
    }


config = RegistrationRulesSettings()
