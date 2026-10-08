from __future__ import annotations

from freedom_ls.messaging_policy.models import FLAG_NAMES


def test_the_flag_names_are_the_three_messaging_flags() -> None:
    assert set(FLAG_NAMES) == {
        "learner_to_educator",
        "learner_to_cohort_peer",
        "learner_to_course_peer",
    }
