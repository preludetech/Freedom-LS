import re
from copy import deepcopy
from functools import cache

import markdown
import nh3
from django_cotton.compiler_regex import CottonCompiler
from markdown.preprocessors import Preprocessor

from django.http import HttpRequest
from django.template import engines
from django.utils.safestring import SafeString, mark_safe

from freedom_ls.markdown_rendering.config import config

_cotton_compiler = CottonCompiler()


# md_in_html converts the body of an element marked markdown="1" only when its
# parent is marked too, so a card inside a grid needs the grid marked. Under an
# unmarked parent (raw HTML such as <div>, or a widget missing from
# MARKDOWN_BODY_TAGS) the body stays raw and the element keeps markdown="1";
# the widget template sees that and converts the body itself with
# {% markdown_body %}.
#
# An opening tag counts at the start of a line or straight after another tag.
# Inline code spans are matched first and returned untouched, so a tag quoted
# in inline code (`<c-card>`) is left alone.
@cache
def _markdown_body_opening(tags: tuple[str, ...]) -> re.Pattern[str]:
    return re.compile(
        r"(?P<code>(?P<ticks>`+).*?(?P=ticks))"
        r"|(?P<lead>^|>)(?P<space>\s*)<(?P<tag>"
        + "|".join(map(re.escape, tags))
        + r")(?=[\s>/])",
        re.MULTILINE,
    )


def _mark_opening(match: re.Match[str]) -> str:
    if match["code"] is not None:
        return match["code"]
    return f'{match["lead"]}{match["space"]}<{match["tag"]} markdown="1"'


class _MarkMarkdownBodies(Preprocessor):
    """Ask md_in_html to convert the body of every widget whose body is markdown."""

    def run(self, lines: list[str]) -> list[str]:
        pattern = _markdown_body_opening(tuple(config.MARKDOWN_BODY_TAGS))
        text = pattern.sub(_mark_opening, "\n".join(lines))
        return text.split("\n")


def render_markdown(
    markdown_text: str,
    request: HttpRequest | None,
    context: dict[str, object] | None = None,
) -> SafeString:
    context = context or {}

    md = markdown.Markdown(
        extensions=[
            "fenced_code",
            "md_in_html",
            "mdx_headdown",
            "tables",
            # Renders GitHub-style `- [ ]` / `- [x]` task lists as read-only
            # (disabled) checkbox inputs. Powers the `checklist` admonition.
            "pymdownx.tasklist",
        ]
    )
    md.parser.blockprocessors.deregister("code")  # Disable indented code blocks
    # Runs after fenced_code (25) has stashed code blocks and before md_in_html's
    # raw-HTML preprocessor (20) reads the markers.
    md.preprocessors.register(_MarkMarkdownBodies(md), "mark_markdown_bodies", 22)

    for key in config.MARKDOWN_ALLOWED_TAGS:
        md.block_level_elements.append(key)

    rendered_content = md.convert(markdown_text)

    # now clean it

    allowed_attribute_tags = config.MARKDOWN_ALLOWED_TAGS

    allowed_tags = deepcopy(nh3.ALLOWED_TAGS)
    allowed_tags.update(allowed_attribute_tags.keys())

    attributes = deepcopy(nh3.ALLOWED_ATTRIBUTES)
    for k, v in allowed_attribute_tags.items():
        attributes[k] = set(v)
    # A body left unconverted under an unmarked parent keeps markdown="1", so
    # its widget template knows to convert it.
    for tag in config.MARKDOWN_BODY_TAGS:
        if tag in attributes:
            attributes[tag].add("markdown")

    # Permit the read-only checkbox markup emitted by pymdownx.tasklist. The
    # checkboxes are always rendered `disabled`, so they carry no interactive
    # capability; allowing the tag through lets `- [ ]` task lists survive
    # sanitising. The `class` hooks let the frontend style the list.
    allowed_tags.add("input")
    attributes["input"] = {"type", "checked", "disabled", "class"}
    attributes["li"] = {"class"}
    attributes["ul"] = {"class"}

    rendered_content = nh3.clean(
        rendered_content, tags=allowed_tags, attributes=attributes
    )

    # do the cotton rendering

    if config.MARKDOWN_TEMPLATE_RENDER_ON:
        # Cotton's loader normally compiles `<c-foo>` to `{% cotton foo %}` when
        # reading templates from disk. Since we're rendering from a string we
        # have to invoke the compiler directly before handing the source to the
        # template engine.
        compiled = _cotton_compiler.process(rendered_content)
        template = engines["django"].from_string(compiled)
        # Template.render already returns SafeString; the backend stub types it as str.
        content = SafeString(template.render(context, request))  # nosec B703 B308
    else:
        # Safe: content is sanitized by nh3.clean() above with strict allowlist
        content = mark_safe(rendered_content)  # noqa: S308  # nosec B308 B703

    return content
