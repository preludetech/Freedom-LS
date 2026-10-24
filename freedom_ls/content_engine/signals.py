"""Signals sent by the content_engine app."""

from __future__ import annotations

from django.dispatch import Signal

# Sent once per load, after every collection's children are written and inside
# the load's transaction, with `site`, `created` (the ContentCollectionItem rows
# this load made) and `written` (every row it touched, created ones included).
# A receiver that raises rolls the load back.
collection_items_synced = Signal()
