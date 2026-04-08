from freedom_ls.feedback.registry import (
    _registry,
    get_trigger_points,
    is_valid_trigger_point,
    register_trigger_point,
)


def test_register_and_retrieve_trigger_points():
    """Test registering and retrieving trigger points."""
    # The app's ready() registers course_completed and topic_completed
    points = get_trigger_points()
    assert "course_completed" in points
    assert "topic_completed" in points


def test_is_valid_trigger_point_returns_true_for_registered():
    assert is_valid_trigger_point("course_completed") is True


def test_is_valid_trigger_point_returns_false_for_unregistered():
    assert is_valid_trigger_point("nonexistent_trigger") is False


def test_register_custom_trigger_point():
    register_trigger_point("custom_trigger", "A custom trigger")
    assert is_valid_trigger_point("custom_trigger") is True
    assert get_trigger_points()["custom_trigger"] == "A custom trigger"
    # Clean up
    del _registry["custom_trigger"]
