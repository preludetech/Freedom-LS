from django import template
from django.utils.safestring import SafeString

from freedom_ls.icons.backend import render_icon_html

register = template.Library()


@register.simple_tag
def icon(
    name: str,
    variant: str = "outline",
    css_class: str = "size-5",
    aria_label: str = "",
) -> str:
    html = render_icon_html(
        name, variant=variant, css_class=css_class, aria_label=aria_label
    )
    # HTML is generated internally by our renderer (not user input), safe to render
    return SafeString(html)  # nosec B703
