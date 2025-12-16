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

    allowed_attribute_tags = settings.MARKDOWN_ALLOWED_TAGS

    allowed_tags = set(allowed_attribute_tags)

    attributes = deepcopy(nh3.ALLOWED_ATTRIBUTES)
    for k, v in allowed_attribute_tags.items():
        attributes[k] = v

    markdown_text = nh3.clean(markdown_text, tags=allowed_tags, attributes=attributes)
    # [s for s in markdown_text.split("\n") if "c-p" in s]

    if settings.MARKDOWN_TEMPLATE_RENDER_ON:
        os.makedirs("/tmp/lms_templates", exist_ok=True)
        temp = tempfile.NamedTemporaryFile(prefix="template_", dir="/tmp/lms_templates")

        temp.write(str.encode(markdown_text))
        temp.seek(0)
        content = loader.render_to_string(
            Path(temp.name).stem, context=context, request=request, using=None
        )
    else:
        content = markdown_text

    md = markdown.Markdown(extensions=["fenced_code", "mdx_headdown"])

    return mark_safe(md.convert(content))
