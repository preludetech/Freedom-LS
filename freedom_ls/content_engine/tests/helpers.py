"""Helpers shared by tests of the content tree."""

from __future__ import annotations

from freedom_ls.content_engine.models import ContentCollectionItem, Course, Topic
from freedom_ls.form_engine.models import Form


def collection_item_for(course: Course, child: Form | Topic) -> ContentCollectionItem:
    """The collection item placing `child` in `course`.

    Read off a freshly loaded Course: `collection_items()` memoizes per
    instance, so a test that attaches more content between two lookups would
    otherwise be handed the list as it stood at the first one.
    """
    placed: Course = Course.objects.get(pk=course.pk)
    for collection_item in placed.viewable_collection_items():
        if collection_item.child == child:
            return collection_item
    raise AssertionError(f"{child} is not placed in {course}.")
