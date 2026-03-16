import pytest

from freedom_ls.webhooks.registry import get_event_type_registry, validate_event_type


class TestGetEventTypeRegistry:
    def test_returns_dict_of_event_types(self) -> None:
        registry = get_event_type_registry()
        assert isinstance(registry, dict)
        assert "user.registered" in registry
        assert registry["user.registered"] == "User registered"


class TestValidateEventType:
    def test_valid_event_type_does_not_raise(self) -> None:
        validate_event_type("user.registered")
        validate_event_type("course.completed")
        validate_event_type("course.registered")

    def test_invalid_event_type_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown webhook event type"):
            validate_event_type("nonexistent.event")

    def test_empty_string_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown webhook event type"):
            validate_event_type("")
