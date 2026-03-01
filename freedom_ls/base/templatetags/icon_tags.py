from django import template

from freedom_ls.base.icons import ICONS

register = template.Library()


@register.filter
def icon_from_name(name: str, force: str = "") -> str:
    """Resolve a semantic icon name to a heroicon name.

    Used internally by the <c-icon /> cotton component.
    If force is truthy, bypasses the registry and returns name as-is
    (for one-off heroicon names not in the registry).
    """
    if str(force).lower() in ("true", "1", "yes"):
        return name
    return ICONS[name]  # KeyError if not in registry
