import pytest

from freedom_ls.educator_interface.panels.common.badges import active_status_badge


@pytest.mark.parametrize(
    ("is_active", "label", "tone"),
    [(True, "Active", "success"), (False, "Inactive", "muted")],
)
def test_active_status_badge_has_one_label_and_tone_per_state(
    is_active: bool, label: str, tone: str
):
    badge = active_status_badge(is_active)

    assert (badge.label, badge.tone) == (label, tone)
