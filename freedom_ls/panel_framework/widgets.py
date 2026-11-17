"""Form widgets the framework swaps in for Django's defaults."""

from __future__ import annotations

import os

from django import forms

__all__ = ["PanelClearableFileInput"]


class PanelClearableFileInput(forms.ClearableFileInput):
    """A file input that names the current file without linking to it."""

    template_name = "panel_framework/widgets/clearable_file_input.html"
    use_fieldset = False
    clear_checkbox_label = "Remove"
    initial_text = "Current file:"

    def is_initial(self, value: object) -> bool:
        # Not `.url`: on private storage reading it signs a URL, and a
        # storage with no URL support raises.
        return bool(getattr(value, "name", ""))

    def get_context(
        self, name: str, value: object, attrs: dict[str, object] | None
    ) -> dict[str, object]:
        context = super().get_context(name, value, attrs)
        # The basename alone: the full name is the storage key.
        context["widget"]["current_file_name"] = (
            os.path.basename(getattr(value, "name", ""))
            if self.is_initial(value)
            else ""
        )
        # Django leaves the Remove tick in the attrs the file input
        # prints; it belongs on the checkbox alone.
        context["widget"]["checked"] = context["widget"]["attrs"].pop("checked", False)
        return context
