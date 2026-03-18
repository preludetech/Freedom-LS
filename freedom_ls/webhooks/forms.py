from django_ace import AceWidget

from django import forms
from django.utils.html import json_script
from django.utils.safestring import SafeString

from freedom_ls.webhooks.models import WebhookEndpoint, WebhookSecret
from freedom_ls.webhooks.presets import WEBHOOK_PRESETS, get_preset_choices
from freedom_ls.webhooks.registry import get_event_type_registry

TEMPLATE_HELP_TEXT = (
    "Jinja2 template. Available variables: "
    "event.id, event.type, event.timestamp, event.data.*, secrets.*"
)


class EventTypeWidget(forms.CheckboxSelectMultiple):
    """Checkbox widget for selecting event types from the registry."""

    pass


class EventTypeField(forms.MultipleChoiceField):
    """Field that renders event type checkboxes and stores values as JSON."""

    widget = EventTypeWidget

    def __init__(self, **kwargs) -> None:
        registry = get_event_type_registry()
        choices = [(key, label) for key, label in registry.items()]
        kwargs.setdefault("choices", choices)
        kwargs.setdefault("required", True)
        super().__init__(**kwargs)


class PresetSelectWidget(forms.Select):
    """Select widget that also renders preset data as a JSON script block."""

    class Media:
        js = ("webhooks/js/preset_selector.js",)

    def render(
        self,
        name: str,
        value: object,
        attrs: dict[str, object] | None = None,
        renderer: forms.renderers.BaseRenderer | None = None,
    ) -> SafeString:
        select_html = super().render(name, value, attrs, renderer)
        preset_data = {
            slug: {
                "default_url": p.default_url,
                "http_method": p.http_method,
                "content_type": p.content_type,
                "headers_template": p.headers_template,
                "body_template": p.body_template,
            }
            for slug, p in WEBHOOK_PRESETS.items()
        }
        script_tag = json_script(preset_data, "webhook-preset-data")
        return SafeString(str(select_html) + str(script_tag))  # nosec B703 - both from Django's safe rendering


class PresetChoiceField(forms.ChoiceField):
    """Non-model field for selecting a webhook preset (populates other fields via JS)."""

    widget = PresetSelectWidget

    def __init__(self, **kwargs) -> None:
        choices = [("", "\u2014 No preset \u2014"), *get_preset_choices()]
        kwargs.setdefault("choices", choices)
        kwargs.setdefault("required", False)
        kwargs.setdefault("label", "Preset")
        super().__init__(**kwargs)


class WebhookEndpointForm(forms.ModelForm):
    event_types = EventTypeField()
    preset_slug = PresetChoiceField()

    class Meta:
        model = WebhookEndpoint
        fields = [
            "url",
            "description",
            "event_types",
            "is_active",
            "http_method",
            "content_type",
            "auth_type",
            "headers_template",
            "body_template",
            "preset_slug",
        ]
        widgets = {
            "headers_template": AceWidget(
                mode="django",
                theme="chrome",
                wordwrap=True,
                showprintmargin=False,
                width="100%",
                height="200px",
            ),
            "body_template": AceWidget(
                mode="django",
                theme="chrome",
                wordwrap=True,
                showprintmargin=False,
                width="100%",
                height="300px",
            ),
        }
        help_texts = {
            "headers_template": TEMPLATE_HELP_TEXT,
            "body_template": TEMPLATE_HELP_TEXT,
        }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.initial["event_types"] = self.instance.event_types
            # Preserve current preset_slug as a valid choice even if
            # the preset definition has been removed from code.
            current_slug = self.instance.preset_slug
            if current_slug and isinstance(
                self.fields["preset_slug"], forms.ChoiceField
            ):
                preset_field = self.fields["preset_slug"]
                if not callable(preset_field.choices):
                    choices_list = list(preset_field.choices)
                    existing_slugs = {c[0] for c in choices_list}
                    if current_slug not in existing_slugs:
                        preset_field.choices = [
                            *choices_list,
                            (current_slug, f"{current_slug} (unavailable)"),
                        ]


class WebhookSecretForm(forms.ModelForm):
    class Meta:
        model = WebhookSecret
        fields = ["name", "description", "encrypted_value"]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fields["encrypted_value"].label = "Secret Value"
        if self.instance and self.instance.pk:
            # On edit: use PasswordInput with placeholder
            self.fields["encrypted_value"].widget = forms.PasswordInput(
                attrs={"placeholder": "Enter new value to change"},
                render_value=True,
            )
            self.fields["encrypted_value"].required = False
        else:
            # On create: use standard TextInput
            self.fields["encrypted_value"].widget = forms.TextInput()

    def clean_name(self) -> str:
        name: str = self.cleaned_data.get("name", "")
        qs = WebhookSecret.objects.filter(name=name)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("A secret with this name already exists.")
        return name

    def clean_encrypted_value(self) -> str:
        value: str = self.cleaned_data.get("encrypted_value", "")
        if not value and self.instance and self.instance.pk:
            # Keep the existing encrypted value when field is left blank on edit
            return str(self.instance.encrypted_value)
        return value
