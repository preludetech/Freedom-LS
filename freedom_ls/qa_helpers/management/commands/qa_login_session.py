"""Create a logged-in session for a user and print its cookie.

For users a tester cannot sign in as with a password, such as one whose
password is unusable. The session is written to the session store exactly as
``django.contrib.auth.login`` would write it; set the printed cookie in the
browser for the site's host and reload.

The session does not record a login: ``last_login`` is left untouched, so a
pending account stays pending.

Usage:
    uv run python manage.py qa_login_session --email qa-nopassword@example.com
"""

from __future__ import annotations

from importlib import import_module

import djclick as click

from django.conf import settings
from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY

from freedom_ls.accounts.models import User

BACKEND = "django.contrib.auth.backends.ModelBackend"


@click.command()
@click.option("--email", required=True)
def command(email: str) -> None:
    user = User._base_manager.select_related("site").get(email=email)
    store = import_module(settings.SESSION_ENGINE).SessionStore()
    store[SESSION_KEY] = str(user.pk)
    store[BACKEND_SESSION_KEY] = BACKEND
    store[HASH_SESSION_KEY] = user.get_session_auth_hash()
    store.create()

    click.echo(f"User: {user.email} (pk {user.pk}) on {user.site}")
    click.echo(f"Cookie name : {settings.SESSION_COOKIE_NAME}")
    click.echo(f"Cookie value: {store.session_key}")
    click.echo(
        "In the browser, on the site's host, run: "
        f"document.cookie = '{settings.SESSION_COOKIE_NAME}={store.session_key}; path=/'"
        " and reload."
    )
