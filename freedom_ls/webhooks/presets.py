from dataclasses import dataclass


@dataclass(frozen=True)
class WebhookPreset:
    name: str
    slug: str
    description: str
    default_url: str
    http_method: str
    content_type: str
    headers_template: str
    body_template: str


WEBHOOK_PRESETS: dict[str, WebhookPreset] = {}


def _register(preset: WebhookPreset) -> None:
    WEBHOOK_PRESETS[preset.slug] = preset


def get_preset_choices() -> list[tuple[str, str]]:
    return [(slug, p.name) for slug, p in WEBHOOK_PRESETS.items()]


# --- Brevo Track Event (v3) ---
_register(
    WebhookPreset(
        name="Brevo \u2014 Track Event",
        slug="brevo-track-event",
        description="Calls Brevo's Events API to trigger automations. Required secrets: brevo_api_key",
        default_url="https://api.brevo.com/v3/events",
        http_method="POST",
        content_type="application/json",
        headers_template='{\n  "api-key": "{{ secrets.brevo_api_key }}",\n  "accept": "application/json"\n}',
        body_template='{\n  "event_name": "{{ event.type | replace(\'.\', \'_\') }}",\n  "identifiers": {\n    "email_id": "{{ event.data.user_email }}"\n  },\n  "event_properties": {{ event.data | tojson }}\n}',
    )
)
