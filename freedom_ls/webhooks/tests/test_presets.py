import json

import pytest

from freedom_ls.webhooks.presets import (
    WEBHOOK_PRESETS,
    WebhookPreset,
    get_preset_choices,
)
from freedom_ls.webhooks.rendering import render_template


class TestGetPresetChoices:
    def test_returns_non_empty_list(self) -> None:
        choices = get_preset_choices()
        assert len(choices) > 0

    def test_returns_list_of_slug_name_tuples(self) -> None:
        choices = get_preset_choices()
        for slug, name in choices:
            assert isinstance(slug, str)
            assert isinstance(name, str)
            assert slug in WEBHOOK_PRESETS
            assert WEBHOOK_PRESETS[slug].name == name


class TestPresetIsFrozen:
    def test_preset_is_frozen_dataclass(self) -> None:
        preset = WEBHOOK_PRESETS["brevo-create-contact"]
        assert isinstance(preset, WebhookPreset)
        with pytest.raises(AttributeError):
            preset.name = "changed"


class TestBrevoCreateContactPreset:
    def test_preset_exists(self) -> None:
        assert "brevo-create-contact" in WEBHOOK_PRESETS

    def test_preset_has_correct_defaults(self) -> None:
        preset = WEBHOOK_PRESETS["brevo-create-contact"]
        assert preset.http_method == "POST"
        assert preset.content_type == "application/json"
        assert preset.default_url == "https://api.brevo.com/v3/contacts"

    def test_body_template_renders_valid_json(self) -> None:
        preset = WEBHOOK_PRESETS["brevo-create-contact"]
        context = {
            "event": {
                "id": "sample-uuid-0000",
                "type": "user.registered",
                "timestamp": "2026-01-01T00:00:00Z",
                "data": {
                    "user_id": "sample-uuid-1234",
                    "user_email": "test@example.com",
                    "first_name": "Jane",
                    "last_name": "Doe",
                },
            },
            "secrets": {
                "brevo_api_key": "xkeysib-test-key",  # pragma: allowlist secret
                "brevo_list_id": "6",
            },
        }
        rendered = render_template(preset.body_template, context)
        parsed = json.loads(rendered)
        assert parsed["email"] == "test@example.com"
        assert parsed["attributes"]["FNAME"] == "Jane"
        assert parsed["attributes"]["LNAME"] == "Doe"
        assert parsed["listIds"] == [6]
        assert parsed["updateEnabled"] is True
        assert parsed["emailBlacklisted"] is False
        assert parsed["smsBlacklisted"] is False

    def test_headers_template_renders_with_secret(self) -> None:
        preset = WEBHOOK_PRESETS["brevo-create-contact"]
        context = {
            "secrets": {
                "brevo_api_key": "xkeysib-test-key",  # pragma: allowlist secret
            },
        }
        rendered = render_template(preset.headers_template, context)
        parsed = json.loads(rendered)
        assert parsed["api-key"] == "xkeysib-test-key"
        assert parsed["accept"] == "application/json"
