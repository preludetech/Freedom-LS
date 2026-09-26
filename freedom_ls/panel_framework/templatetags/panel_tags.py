import re

from django import template
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.safestring import SafeString

from freedom_ls.panel_framework.actions import PanelAction
from freedom_ls.panel_framework.context import PanelContext
from freedom_ls.panel_framework.panels import Panel

register = template.Library()


@register.simple_tag
def render_panel(panel: Panel) -> SafeString:
    """Render a bound panel through its own template and context.

    `{% include %}` cannot take a context dict, so this tag is how a template
    renders another panel. It renders against the panel's own request, so
    context processors run as they would for a page.
    """
    return render_to_string(
        panel.template_name, panel.get_context_data(), request=panel.request
    )


@register.simple_tag
def render_action(action: PanelAction, ctx: PanelContext) -> SafeString:
    """Render an action for the panel or view whose context is `ctx`."""
    return render_to_string(
        action.template_name, action.get_context_data(ctx), request=ctx.request
    )


@register.simple_tag(takes_context=True)
def resolve_url_path_template(
    context: template.Context, obj: object, url_name: str, path_template: str
) -> str:
    """Build a URL by substituting {attr} placeholders in the path template
    with attribute values from the object, then reversing the URL.

    Usage: {% resolve_url_path_template object "educator_interface:interface" "cohorts/{pk}" %}
    Produces: /educator/cohorts/42

    Merges in request.panel_url_kwargs — the same extra reverse() kwargs a
    hosting view supplies to the menu and breadcrumb builders — so a link
    built from a table cell carries whatever scope segment the current
    request needs, without this tag ever knowing what that segment means.
    """

    def replace_attr(match: re.Match[str]) -> str:
        attr_name = match.group(1)
        value = obj
        for part in attr_name.split("."):
            value = getattr(value, part)
        if callable(value):
            value = value()
        return str(value)

    path_string = re.sub(r"\{(\w+(?:\.\w+)*)\}", replace_attr, path_template)
    request = context.get("request")
    extra_url_kwargs: dict[str, str] = getattr(request, "panel_url_kwargs", {})
    return reverse(url_name, kwargs={"path_string": path_string, **extra_url_kwargs})
