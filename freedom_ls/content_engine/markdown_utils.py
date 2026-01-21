from django.template import loader
import tempfile
from pathlib import Path
import markdown
from django.utils.safestring import mark_safe
from django.conf import settings
import nh3
from copy import deepcopy
import os


def render_markdown(markdown_text, request, context=None):
    context = context or {}

    md = markdown.Markdown(extensions=["fenced_code", "mdx_headdown", "tables"])
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

    rendered_content = nh3.clean(
        rendered_content, tags=allowed_tags, attributes=attributes
    )

    # do the cotton rendering

    if settings.MARKDOWN_TEMPLATE_RENDER_ON:
        os.makedirs("/tmp/lms_templates", exist_ok=True)
        temp = tempfile.NamedTemporaryFile(prefix="template_", dir="/tmp/lms_templates")

        temp.write(str.encode(rendered_content))
        temp.seek(0)
        content = loader.render_to_string(
            Path(temp.name).stem, context=context, request=request, using=None
        )
    else:
        content = rendered_content

    return mark_safe(content)
