import re
from copy import deepcopy

import markdown
import nh3
from django_cotton.compiler_regex import CottonCompiler
from markdown.preprocessors import Preprocessor

from django.http import HttpRequest
from django.template import engines
from django.utils.safestring import SafeString, mark_safe

from freedom_ls.markdown_rendering.config import config

_cotton_compiler = CottonCompiler()

# The six slot widgets, plus c-slot and the layout wrappers c-grid and
# c-image-grid that can hold them. md_in_html converts the body of an element
# marked markdown="1" only when its parent is marked too, so a card inside a
# grid needs the grid marked. Widget children of a marked element stay raw.
MARKDOWN_BODY_TAGS: tuple[str, ...] = (
    "c-accordion",
    "c-admonition",
    "c-card",
    "c-flashcard",
    "c-pull-quote",
    "c-table",
    "c-slot",
    "c-grid",
    "c-image-grid",
)

# An opening tag at the start of a line or straight after another tag, so a
# tag quoted in inline code (`<c-card>`) is left alone.
_MARKDOWN_BODY_OPENING = re.compile(
    r"(^|>)(\s*)<(" + "|".join(map(re.escape, MARKDOWN_BODY_TAGS)) + r")(?=[\s>/])",
    re.MULTILINE,
)


class _MarkMarkdownBodies(Preprocessor):
    """Ask md_in_html to convert the body of every widget whose body is markdown."""

    def run(self, lines: list[str]) -> list[str]:
        text = _MARKDOWN_BODY_OPENING.sub(r'\1\2<\3 markdown="1"', "\n".join(lines))
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
        attributes[k] = v

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
