"""
WSGI config for config project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

from django.core.wsgi import get_wsgi_application

# DJANGO_SETTINGS_MODULE is deliberately left undefaulted. FLS has no canonical settings
# module -- settings_dev and settings_prod are both real choices -- so the caller names one,
# and a process that forgets stops at Django's own error instead of booting on a guess.
application = get_wsgi_application()
