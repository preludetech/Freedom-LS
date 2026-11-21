from typing import cast

import pytest

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.educator_interface.panels.common.badges import (
    active_status_badge,
    learner_status_badge,
)
from freedom_ls.learner_management.factories import LearnerFactory
from freedom_ls.learner_management.models import Learner
from freedom_ls.organisations.factories import OrganisationFactory


@pytest.mark.parametrize(
    ("is_active", "label", "tone"),
    [(True, "Active", "success"), (False, "Inactive", "muted")],
)
def test_active_status_badge_has_one_label_and_tone_per_state(
    is_active: bool, label: str, tone: str
):
    badge = active_status_badge(is_active)

    assert (badge.label, badge.tone) == (label, tone)


def _learner_in_state(state: str) -> Learner:
    user = UserFactory()
    if state == "pending":
        user.set_unusable_password()
        user.save()
    learner = cast(
        Learner,
        LearnerFactory(
            user=user, organisation=OrganisationFactory(), is_active=state != "inactive"
        ),
    )
    return learner


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("state", "label", "tone"),
    [
        ("active", "Active", "success"),
        ("pending", "Pending", "info"),
        ("inactive", "Inactive", "muted"),
    ],
)
def test_learner_status_badge_has_one_label_and_tone_per_state(
    mock_site_context, state: str, label: str, tone: str
):
    badge = learner_status_badge(_learner_in_state(state))

    assert (badge.label, badge.tone) == (label, tone)
