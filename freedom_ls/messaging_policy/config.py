from __future__ import annotations

from freedom_ls.base.app_settings import AppSettings, Setting


class MessagingPolicyConfig(AppSettings):
    MESSAGING_DEFAULT_FLAGS: dict[str, str]
    MESSAGING_OFFERED_EDUCATOR_ROLES: list[str]

    declared_settings = {
        "MESSAGING_DEFAULT_FLAGS": Setting(
            default={
                "learner_to_educator": "closed",
                "learner_to_cohort_peer": "closed",
                "learner_to_course_peer": "closed",
            }
        ),
        # An install without cohorts adds "organisation_admin".
        "MESSAGING_OFFERED_EDUCATOR_ROLES": Setting(default=["cohort_admin"]),
    }


config = MessagingPolicyConfig()
