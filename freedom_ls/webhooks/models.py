import ipaddress
import json
import secrets
import socket
from urllib.parse import urlparse

import jinja2
from encrypted_fields.fields import EncryptedTextField  # type: ignore[import-untyped]
from jinja2.sandbox import SandboxedEnvironment

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models

from freedom_ls.base.webhook_event_types import WEBHOOK_EVENT_TYPE_SAMPLES
from freedom_ls.site_aware_models.models import SiteAwareModel
from freedom_ls.webhooks.registry import validate_event_type

SECRET_NAME_VALIDATOR = RegexValidator(
    regex=r"^[a-zA-Z_][a-zA-Z0-9_]*$",
    message="Name must start with a letter or underscore and contain only letters, digits, and underscores.",
)

HTTP_METHOD_CHOICES = [
    ("GET", "GET"),
    ("POST", "POST"),
    ("PUT", "PUT"),
    ("PATCH", "PATCH"),
    ("DELETE", "DELETE"),
]

AUTH_TYPE_CHOICES = [
    ("signing", "HMAC Signing (Standard)"),
    ("none", "None (Custom Auth via Headers)"),
]

STATUS_CHOICES = [
    ("pending", "Pending"),
    ("success", "Success"),
    ("failed", "Failed"),
    ("permanent_failure", "Permanent Failure"),
    ("dead_letter", "Dead letter"),
]


class WebhookEndpoint(SiteAwareModel):
    url = models.URLField(max_length=2048)
    description = models.CharField(max_length=200)
    secret = models.CharField(max_length=128, editable=False)
    event_types = models.JSONField(default=list)
    http_method = models.CharField(
        max_length=7, choices=HTTP_METHOD_CHOICES, blank=True, default=""
    )
    content_type = models.CharField(max_length=100, blank=True, default="")
    headers_template = models.TextField(blank=True, default="")
    body_template = models.TextField(blank=True, default="")
    auth_type = models.CharField(
        max_length=10, choices=AUTH_TYPE_CHOICES, default="signing"
    )
    preset_slug = models.CharField(max_length=100, blank=True, default="")
    is_active = models.BooleanField(
        default=True,
        help_text="User intent: toggled by admin enable/disable actions only.",
    )
    failure_count = models.PositiveIntegerField(default=0)
    disabled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Circuit breaker state: set when failure threshold is reached, cleared on successful delivery.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def has_transformation(self) -> bool:
        return bool(self.body_template)

    def __str__(self) -> str:
        return self.description

    def save(self, *args: object, **kwargs: object) -> None:
        if not self.secret:
            self.secret = secrets.token_urlsafe(48)
        super().save(*args, **kwargs)

    def clean(self) -> None:
        super().clean()
        # Validate event types against registry
        for event_type in self.event_types:
            try:
                validate_event_type(event_type)
            except ValueError as e:
                raise ValidationError({"event_types": str(e)}) from e

        # SSRF protection (production only)
        if not settings.DEBUG and self.url:
            self._validate_url_ssrf()

        # Transformation field validation
        self._validate_transformation_fields()

    def _validate_url_ssrf(self) -> None:
        """Validate URL against SSRF attacks: reject private IPs, non-HTTP(S) schemes."""
        parsed = urlparse(self.url)

        # Reject non-HTTP(S) schemes
        if parsed.scheme not in ("http", "https"):
            raise ValidationError({"url": "Webhook URLs must use HTTP or HTTPS."})

        hostname = parsed.hostname
        if not hostname:
            raise ValidationError({"url": "Invalid URL: no hostname."})

        # Resolve hostname and check all resolved addresses
        try:
            addr_infos = socket.getaddrinfo(hostname, parsed.port or 443)
        except socket.gaierror as e:
            raise ValidationError(
                {"url": f"Could not resolve hostname: {hostname}"}
            ) from e

        for addr_info in addr_infos:
            ip_str = addr_info[4][0]
            try:
                addr = ipaddress.ip_address(ip_str)
            except ValueError:
                continue
            if addr.is_private or addr.is_loopback or addr.is_link_local:
                raise ValidationError(
                    {
                        "url": (
                            "Webhook URLs must not point to private or loopback addresses. "
                            f"Resolved {hostname} to {ip_str}."
                        )
                    }
                )

    def _validate_transformation_fields(self) -> None:
        """Validate Jinja2 templates and transformation field consistency."""
        transformation_fields = {
            "http_method": self.http_method,
            "content_type": self.content_type,
            "headers_template": self.headers_template,
            "auth_type": self.auth_type if self.auth_type != "signing" else "",
        }
        has_any_transformation_field = any(transformation_fields.values())

        if has_any_transformation_field and not self.has_transformation:
            raise ValidationError(
                {
                    "body_template": (
                        "body_template is required when other transformation fields are set."
                    )
                }
            )

        if not self.has_transformation:
            return

        env = SandboxedEnvironment(undefined=jinja2.StrictUndefined)

        # Validate body_template syntax
        self._validate_jinja2_template(env, self.body_template, "body_template")

        # If content_type is application/json, validate rendered output is valid JSON
        if self.content_type == "application/json":
            self._validate_json_template_output(
                env, self.body_template, "body_template"
            )

        # Validate headers_template if set
        if self.headers_template:
            self._validate_jinja2_template(
                env, self.headers_template, "headers_template"
            )
            self._validate_headers_template_output(env, self.headers_template)

    def _validate_jinja2_template(
        self, env: SandboxedEnvironment, template_str: str, field_name: str
    ) -> None:
        """Parse a Jinja2 template and raise ValidationError on syntax errors."""
        try:
            ast = env.parse(template_str)
        except jinja2.TemplateSyntaxError as e:
            raise ValidationError({field_name: f"Jinja2 syntax error: {e}"}) from e

        # TODO: Spec requires warning (not error) for undeclared variables.
        # Use jinja2.meta.find_undeclared_variables(ast) to detect variables
        # not in {"event", "secrets"}. Django model clean() doesn't support
        # non-blocking warnings, so this needs a form-level or admin-level
        # implementation using django.contrib.messages.
        _ = ast  # parsed AST available for future undeclared-variable check

    def _get_sample_template_context(self) -> dict[str, object]:
        """Return sample context for template validation rendering.

        Uses WEBHOOK_EVENT_TYPE_SAMPLES to provide realistic sample data
        based on the endpoint's configured event types.
        """
        # Use the first subscribed event type, or fall back to first available sample
        event_type = "user.registered"
        if self.event_types:
            event_type = self.event_types[0]

        sample_data = WEBHOOK_EVENT_TYPE_SAMPLES.get(
            event_type, WEBHOOK_EVENT_TYPE_SAMPLES.get("user.registered", {})
        )

        return {
            "event": {
                "id": "sample-uuid-0000",
                "type": event_type,
                "timestamp": "2026-01-01T00:00:00Z",
                "data": sample_data,
            },
            "secrets": {},
        }

    def _try_render_template(
        self, env: SandboxedEnvironment, template_str: str
    ) -> str | None:
        """Attempt to render a template with sample data. Returns rendered string or None if skipped.

        Uses a permissive Undefined subclass so that templates referencing
        secrets (e.g. {{ secrets.brevo_api_key }}) produce placeholder strings
        instead of raising UndefinedError during validation.
        """
        sample_context = self._get_sample_template_context()
        # Use a permissive environment for validation so missing secrets
        # produce placeholder strings rather than raising UndefinedError.
        validation_env = SandboxedEnvironment(undefined=jinja2.DebugUndefined)
        try:
            template = validation_env.from_string(template_str)
            return template.render(**sample_context)
        except jinja2.TemplateError:
            # Other template errors already caught by syntax validation
            return None

    def _validate_json_template_output(
        self, env: SandboxedEnvironment, template_str: str, field_name: str
    ) -> None:
        """Render template with sample data and validate JSON output."""
        rendered = self._try_render_template(env, template_str)
        if rendered is None:
            return

        try:
            json.loads(rendered)
        except json.JSONDecodeError as e:
            raise ValidationError(
                {
                    field_name: (
                        f"Template must produce valid JSON when content_type is application/json. "
                        f"Error: {e}"
                    )
                }
            ) from e

    def _validate_headers_template_output(
        self, env: SandboxedEnvironment, template_str: str
    ) -> None:
        """Validate that headers_template renders to a JSON object."""
        rendered = self._try_render_template(env, template_str)
        if rendered is None:
            return

        try:
            parsed = json.loads(rendered)
        except json.JSONDecodeError as e:
            raise ValidationError(
                {
                    "headers_template": f"Headers template must produce valid JSON. Error: {e}"
                }
            ) from e

        if not isinstance(parsed, dict):
            raise ValidationError(
                {
                    "headers_template": "Headers template must produce a JSON object (not array or scalar)."
                }
            )


class WebhookEvent(SiteAwareModel):
    event_type = models.CharField(max_length=100)
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.event_type} at {self.created_at}"


class WebhookDelivery(SiteAwareModel):
    event = models.ForeignKey(
        WebhookEvent, on_delete=models.CASCADE, related_name="deliveries"
    )
    endpoint = models.ForeignKey(
        WebhookEndpoint, on_delete=models.CASCADE, related_name="deliveries"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    attempt_count = models.PositiveIntegerField(default=0)
    next_retry_at = models.DateTimeField(null=True, blank=True)
    last_status_code = models.PositiveIntegerField(null=True, blank=True)
    last_response_body = models.TextField(blank=True, default="")
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    last_latency_ms = models.PositiveIntegerField(null=True, blank=True)
    last_response_error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Webhook deliveries"

    def __str__(self) -> str:
        return f"Delivery {self.pk} ({self.status})"

    def save(self, *args: object, **kwargs: object) -> None:
        if len(self.last_response_body) > 500:
            self.last_response_body = self.last_response_body[:500]
        super().save(*args, **kwargs)


class WebhookSecret(SiteAwareModel):
    name = models.CharField(
        max_length=100,
        validators=[SECRET_NAME_VALIDATOR],
    )
    description = models.CharField(max_length=200, blank=True, default="")
    encrypted_value = EncryptedTextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("site", "name")]

    def __str__(self) -> str:
        return self.name
