"""Repoint the GenericFKs the form_engine app move left dangling.

The migrations that moved the form models out of ``content_engine`` and into
``form_engine`` change those models' ContentType. Django creates the new
``freedom_ls_form_engine`` ContentType rows and leaves the old
``freedom_ls_content_engine`` ones behind, but nothing rewrites the GenericFKs
that already point at the old rows. ``ContentCollectionItem.child_type`` is one
of those: after migrating, every course item whose child is a Form points at a
ContentType whose ``model_class()`` is now ``None``, and
``Course.children()`` raises ``AttributeError: 'NoneType' object has no
attribute '_base_manager'`` -- so every course containing a quiz is broken in
the browser and in every QA command that reads a course.

Only needed on a dev database that carried form data across the move. Safe and
idempotent: it rewrites nothing once the old ContentType rows are unreferenced,
and it leaves the stale ContentType and Permission rows themselves alone.

Usage:
    uv run python manage.py qa_repair_form_engine_content_types
"""

import djclick as click

from django.contrib.contenttypes.models import ContentType

from freedom_ls.content_engine.models import ContentCollectionItem

MOVED_MODELS = ["form", "formpage", "formcontent", "formquestion", "questionoption"]
OLD_APP_LABEL = "freedom_ls_content_engine"
NEW_APP_LABEL = "freedom_ls_form_engine"


@click.command()
def command() -> None:
    """Point every ContentCollectionItem at the form_engine ContentTypes."""
    total = 0
    for model_name in MOVED_MODELS:
        old = ContentType.objects.filter(
            app_label=OLD_APP_LABEL, model=model_name
        ).first()
        new = ContentType.objects.filter(
            app_label=NEW_APP_LABEL, model=model_name
        ).first()
        if old is None or new is None:
            click.secho(f"  {model_name:<16} nothing to do", fg="yellow")
            continue
        # _base_manager: this is a cross-site repair, and the site-aware
        # manager would narrow it to whatever site is ambient (none, here).
        children = ContentCollectionItem._base_manager.filter(child_type=old).update(
            child_type=new
        )
        collections = ContentCollectionItem._base_manager.filter(
            collection_type=old
        ).update(collection_type=new)
        total += children + collections
        click.secho(
            f"  {model_name:<16} child_type={children:>3}  "
            f"collection_type={collections:>3}",
            fg="green",
        )
    click.secho(
        f"Repointed {total} ContentCollectionItem row(s).", fg="cyan", bold=True
    )
