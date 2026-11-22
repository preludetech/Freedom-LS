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

# Sent once per load that deleted a course's placement of a part the course now lists
# under reference:, inside the load's transaction, with `site` and `courses` (each course
# that lost a placement, once). The course's learning path is shorter from here on, so a
# percentage stored against it is stale. A receiver that raises rolls the load back.
part_placements_removed = Signal()
