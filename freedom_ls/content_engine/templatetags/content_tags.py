from django import template
from freedom_ls.content_engine.models import File, Topic, Form
from freedom_ls.content_engine.markdown_utils import render_markdown

register = template.Library()


@register.filter  # (needs_context=True)
def get_file_by_path(file_path, content_instance):
    """
    Template filter to look up a File object by its file_path.

    Usage: {{ "path/to/image.jpg"|get_file_by_path }}

    """

    if not file_path:
        return None
    file_path = file_path.strip()

    if not file_path:
        return None

    final_path = content_instance.calculate_path_from_root(file_path)

    try:
        return File.objects.get(file_path=final_path)
    except File.DoesNotExist:
        return None
    except File.MultipleObjectsReturned:
        # In case of duplicates, return the first one
        return File.objects.filter(file_path=final_path).first()


@register.simple_tag(takes_context=True)
def markdown(context, value):
    """
    Template tag to render markdown content.

    Usage: {% markdown content %}
    """
    request = context.get("request")
    return render_markdown(value, request)


@register.filter
def get_item(dictionary, key):
    """
    Template filter to get an item from a dictionary by key.

    Usage: {{ my_dict|get_item:my_key }}
    """
    if dictionary is None:
        return None
    return dictionary.get(key)


@register.filter
def get_content_by_path(file_path, content_instance):
    """
    Template filter to look up a content object (Topic or Form) by its file_path.

    Usage: {{ "path/to/content.md"|get_content_by_path:content_instance }}
    """
    if not file_path:
        return None

    final_path = content_instance.calculate_path_from_root(file_path)

    # Try to find as Topic first
    try:
        return Topic.objects.get(file_path=final_path)
    except Topic.DoesNotExist:
        pass
    except Topic.MultipleObjectsReturned:
        return Topic.objects.filter(file_path=final_path).first()

    # Try to find as Form
    try:
        return Form.objects.get(file_path=final_path)
    except Form.DoesNotExist:
        pass
    except Form.MultipleObjectsReturned:
        return Form.objects.filter(file_path=final_path).first()

    return None
