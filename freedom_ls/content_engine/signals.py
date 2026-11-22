"""Signals sent by the content_engine app."""

from __future__ import annotations

from django.dispatch import Signal

# Sent once per load, after every collection's children are written and inside
# the load's transaction, with `site`, `created` (the ContentCollectionItem rows
# this load made), `written` (every row it touched, created ones included) and
# `moved` (a MovedChild for each child the load moved off a row it left behind
# in one of the courses or parts it loaded, whose course placement due dates have
# already followed it). A receiver that raises rolls the load back.
collection_items_synced = Signal()

# Sent inside the load's transaction each time a load deletes a course's placement of a
# part the course now lists under reference:, with `site`, `course` and `part`. The
# placement row is already gone, so the course's learning path no longer holds the part.
# A receiver that deletes rows returns what Django's delete() returns per model, a
# mapping of model label to rows deleted, and content_save adds it to the counts it
# reports. A receiver that raises rolls the load back.
part_placement_removed = Signal()
