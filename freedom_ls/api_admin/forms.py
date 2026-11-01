from unfold.widgets import UnfoldAdminCheckboxSelectMultipleWidget

from django import forms

from freedom_ls.api.models import ApiKey
from freedom_ls.api.scopes import ApiScope


def scope_choices() -> list[tuple[str, str]]:
    return [(scope.value, f"{scope.label}: {scope.description}") for scope in ApiScope]


class ApiKeyAddForm(forms.ModelForm):
    scopes = forms.MultipleChoiceField(
        choices=scope_choices,
        widget=UnfoldAdminCheckboxSelectMultipleWidget,
        help_text="Each API scope names the data a key with it can read.",
    )

    class Meta:
        model = ApiKey
        fields = ["name", "scopes", "expires_at"]
