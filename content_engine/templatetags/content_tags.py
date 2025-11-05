from django import template
from content_engine.models import File

register = template.Library()


@register.filter
def get_file_by_path(file_path):
    """
    Template filter to look up a File object by its file_path.

    Usage: {{ "path/to/image.jpg"|get_file_by_path }}

    Look at the current url and figure out what entity we are looking at.
    It will either be a topic or a form
    The file_path is relative to the entity we are looking at
    """
    if not file_path:
        return None

    try:
        return File.objects.get(file_path=file_path)
    except File.DoesNotExist:
        return None
    except File.MultipleObjectsReturned:
        # In case of duplicates, return the first one
        return File.objects.filter(file_path=file_path).first()
