"""
ASGI config for config project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

from django.core.asgi import get_asgi_application

# DJANGO_SETTINGS_MODULE is deliberately left undefaulted. FLS has no canonical settings
# module -- settings_dev and settings_prod are both real choices -- so the caller names one,
# and a process that forgets stops at Django's own error instead of booting on a guess.
application = get_asgi_application()
