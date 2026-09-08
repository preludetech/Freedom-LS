"""Template tags for the learner dashboard's paginated sections.

Usage:

.. code-block:: django

    {% load dashboard_tags %}
    {% section_page_href section.page_param_name page_obj.next_page_number as href %}
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django import template

from freedom_ls.learner_interface.dashboard_sections import (
    section_page_href as build_section_page_href,
)

if TYPE_CHECKING:
    from django.template.context import RequestContext

register = template.Library()


@register.simple_tag(takes_context=True)
def section_page_href(
    context: RequestContext, param_name: str, page_number: int
) -> str:
    return build_section_page_href(context["request"], param_name, page_number)
