import jinja2
from jinja2.sandbox import SandboxedEnvironment

from freedom_ls.webhooks.models import WebhookEvent, WebhookSecret


def get_jinja2_env() -> SandboxedEnvironment:
    """Return a SandboxedEnvironment with StrictUndefined."""
    return SandboxedEnvironment(undefined=jinja2.StrictUndefined)


def build_event_envelope(event: WebhookEvent) -> dict[str, object]:
    """Build the standard event envelope dict used in template contexts and payloads."""
    return {
        "id": str(event.pk),
        "type": event.event_type,
        "timestamp": event.created_at.isoformat().replace("+00:00", "Z"),
        "data": event.payload,
    }


def build_template_context(event: WebhookEvent, site_id: int) -> dict[str, object]:
    """Build the template context with event data and resolved secrets."""
    secrets_qs = WebhookSecret.objects.filter(site_id=site_id).only(
        "name", "encrypted_value"
    )
    secrets_dict = {s.name: s.encrypted_value for s in secrets_qs}
    return {
        "event": build_event_envelope(event),
        "secrets": secrets_dict,
    }


def render_template(template_str: str, context: dict[str, object]) -> str:
    """Render a Jinja2 template string with the given context."""
    env = get_jinja2_env()
    template = env.from_string(template_str)
    return template.render(**context)
