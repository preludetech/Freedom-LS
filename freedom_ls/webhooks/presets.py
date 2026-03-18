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
        description="Calls Brevo's Events API to trigger automations. Required secrets: brevo_ma_key",
        default_url="https://in-automate.brevo.com/api/v2/trackEvent",
        http_method="POST",
        content_type="application/json",
        headers_template="""{
  "ma-key": "{{ secrets.brevo_ma_key }}",
  "accept": "application/json"
}""",
        body_template="""{
  "email": "{{ event.data.user_email }}",
  "event": "{{ event.type | replace('.', '_') }}",
  "properties": {{ event.data | tojson }}
}""",
    )
)

# --- Discord Webhook ---
_register(
    WebhookPreset(
        name="Discord \u2014 Webhook Message",
        slug="discord-webhook",
        description="Sends event notifications to a Discord channel via webhook.",
        default_url="",
        http_method="POST",
        content_type="application/json",
        headers_template="",
        body_template="""{
  "content": "**{{ event.type }}**\\nEvent ID: {{ event.id }}\\nTimestamp: {{ event.timestamp }}"
}""",
    )
)

# --- Brevo Create/Update Contact ---
_register(
    WebhookPreset(
        name="Brevo — Create/Update Contact",
        slug="brevo-create-contact",
        description="Creates or updates a contact in Brevo when a user registers. Required secrets: brevo_api_key, brevo_list_id",
        default_url="https://api.brevo.com/v3/contacts",
        http_method="POST",
        content_type="application/json",
        headers_template="""{
  "api-key": "{{ secrets.brevo_api_key }}",
  "accept": "application/json"
}""",
        body_template="""{
  "email": "{{ event.data.user_email }}",
  "attributes": {
    "FNAME": "{{ event.data.first_name }}",
    "LNAME": "{{ event.data.last_name }}"
  },
  "listIds": [{{ secrets.brevo_list_id }}],
  "emailBlacklisted": false,
  "smsBlacklisted": false,
  "updateEnabled": true
}""",
    )
)
