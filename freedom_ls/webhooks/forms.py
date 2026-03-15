from typing import Any

from django import forms

from freedom_ls.webhooks.models import WebhookEndpoint
from freedom_ls.webhooks.registry import get_event_type_registry


class EventTypeWidget(forms.CheckboxSelectMultiple):
    """Checkbox widget for selecting event types from the registry."""

    pass


class EventTypeField(forms.MultipleChoiceField):
    """Field that renders event type checkboxes and stores values as JSON."""

    widget = EventTypeWidget

    # Any is needed here because Django form __init__ signatures use complex
    # union types that cannot be expressed without Any when passing through kwargs.
    def __init__(self, **kwargs: Any) -> None:
        registry = get_event_type_registry()
        choices = [(key, label) for key, label in registry.items()]
        kwargs.setdefault("choices", choices)
        kwargs.setdefault("required", True)
        super().__init__(**kwargs)


class WebhookEndpointForm(forms.ModelForm):
    event_types = EventTypeField()

    class Meta:
        model = WebhookEndpoint
        fields = [
            "url",
            "description",
            "event_types",
            "is_active",
        ]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.initial["event_types"] = self.instance.event_types

    def clean_event_types(self) -> list[str]:
        result: list[str] = self.cleaned_data.get("event_types", [])
        return result
