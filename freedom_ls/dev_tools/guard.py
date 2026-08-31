from __future__ import annotations

from django.conf import settings
from django.core.management import CommandError

from freedom_ls.dev_tools.config import config


def require_dev_tools_enabled() -> None:
    """Refuse to run unless this is a development environment or the host opted in.

    Every command in this app calls this first, so a production image that
    happens to install ``freedom_ls.dev_tools`` still can't run one by accident.
    """
    if settings.DEBUG or config.DEV_TOOLS_ENABLED:
        return
    raise CommandError(
        "dev_tools commands are disabled outside development. Set "
        "DEV_TOOLS_ENABLED = True in Django settings to allow this on a "
        "deployment such as staging."
    )
