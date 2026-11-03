from django import template

from freedom_ls.base.templatetags.time_tags import local_time

register = template.Library()

# The tag was first published under this library name, and templates in this
# project and downstream ones load it from here. The implementation lives
# beside the Alpine component it drives.
register.simple_tag(takes_context=True)(local_time)
