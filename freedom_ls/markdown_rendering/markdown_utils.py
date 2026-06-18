from copy import deepcopy

import markdown
import nh3
from django_cotton.compiler_regex import CottonCompiler

from django.conf import settings
from django.template import engines
from django.utils.safestring import mark_safe

_cotton_compiler = CottonCompiler()


def render_markdown(markdown_text, request, context=None):
    context = context or {}

    md = markdown.Markdown(
        extensions=[
            "fenced_code",
            "mdx_headdown",
            "tables",
            # Renders GitHub-style `- [ ]` / `- [x]` task lists as read-only
            # (disabled) checkbox inputs. Powers the `checklist` admonition.
            "pymdownx.tasklist",
        ]
    )
    md.parser.blockprocessors.deregister("code")  # Disable indented code blocks

    for key in settings.MARKDOWN_ALLOWED_TAGS:
        md.block_level_elements.append(key)

    rendered_content = md.convert(markdown_text)

    # now clean it

    allowed_attribute_tags = settings.MARKDOWN_ALLOWED_TAGS

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

    if settings.MARKDOWN_TEMPLATE_RENDER_ON:
        # Cotton's loader normally compiles `<c-foo>` to `{% cotton foo %}` when
        # reading templates from disk. Since we're rendering from a string we
        # have to invoke the compiler directly before handing the source to the
        # template engine.
        compiled = _cotton_compiler.process(rendered_content)
        template = engines["django"].from_string(compiled)
        content = template.render(context, request)
    else:
        # Safe: content is sanitized by nh3.clean() above with strict allowlist
        content = mark_safe(rendered_content)  # noqa: S308  # nosec B308 B703

    return content
