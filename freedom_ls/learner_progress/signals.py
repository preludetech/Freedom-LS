"""Signal receivers for the student_progress app.

Connected by `StudentProgressConfig.ready()`. A receiver in a module nothing imports
is never connected, and fails silently rather than loudly.

The receiver below names its senders, so a new concrete `CourseItemProgress`
subclass does not inherit the behaviour the way it would from a `save()` override —
it needs its own `@receiver` line here.
"""

from __future__ import annotations

from django.contrib.contenttypes.models import ContentType as DjangoContentType
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

from freedom_ls.content_engine.models import (
    ContentCollectionItem,
    Course,
    CoursePart,
    Form,
    Topic,
)
from freedom_ls.student_management.utils import calculate_course_progress_percentage
from freedom_ls.student_progress.models import (
    CourseItemProgress,
    CourseProgress,
    FormProgress,
    TopicProgress,
)
from freedom_ls.student_progress.queries import completed_form_ids_by_user


def update_course_progress_on_completion(
    user: models.Model, content_item: Topic | Form
) -> None:
    """Update progress_percentage on all CourseProgress records affected by completing a content item.

    Traces through ContentCollectionItem to find parent courses (including
    items nested inside CourseParts) and recalculates progress for each.
    """
    # @claude this function is very long. It needs to be refactored
    #
    # topic.courses() should return the courses that a topic is included in
    # form.courses() should return the courses that the form is in
    #
    item_ct = DjangoContentType.objects.get_for_model(content_item)
    course_ct = DjangoContentType.objects.get_for_model(Course)
    course_part_ct = DjangoContentType.objects.get_for_model(CoursePart)

    # Find all ContentCollectionItems where this item is a child
    parent_links = ContentCollectionItem.objects.filter(
        child_type=item_ct, child_id=content_item.id
    )

    direct_course_ids: set = set()
    course_part_ids: set = set()
    for link in parent_links:
        if link.collection_type_id == course_ct.id:
            direct_course_ids.add(link.collection_id)
        elif link.collection_type_id == course_part_ct.id:
            course_part_ids.add(link.collection_id)

    # Batch lookup: find parent Courses for all CourseParts in one query
    course_ids = set(direct_course_ids)
    if course_part_ids:
        course_ids.update(
            ContentCollectionItem.objects.filter(
                child_type=course_part_ct,
                child_id__in=course_part_ids,
                collection_type=course_ct,
            ).values_list("collection_id", flat=True)
        )

    if not course_ids:
        return

    # Get user's completed topic and form IDs
    completed_topic_ids = set(
        TopicProgress.objects.filter(
            user=user, complete_time__isnull=False
        ).values_list("topic_id", flat=True)
    )
    completed_form_ids = completed_form_ids_by_user([user.pk]).get(user.pk, set())

    # Update each affected course's progress (find/create CourseProgress if needed)
    for course in Course.objects.filter(id__in=course_ids):
        percentage = calculate_course_progress_percentage(
            course, completed_topic_ids, completed_form_ids
        )
        CourseProgress.objects.update_or_create(
            user=user,
            course=course,
            defaults={"progress_percentage": percentage},
        )


@receiver(post_save, sender=FormProgress)
@receiver(post_save, sender=TopicProgress)
def recalculate_course_progress_on_save(
    sender: type[CourseItemProgress],
    instance: CourseItemProgress,
    raw: bool = False,
    **kwargs: object,
) -> None:
    """Recalculate course percentages when a save completes a topic or form.

    Only a save fires this — `queryset.update()`, `bulk_create()` and
    `bulk_update()` write rows without it. Code that completes items in bulk has
    to call `update_course_progress_on_completion()` for the affected rows itself.

    `raw` saves come from `loaddata`, which writes exactly the rows in the fixture:
    deriving extra `CourseProgress` rows from a fixture load would invent data the
    fixture author did not ask for.
    """
    if raw:
        return

    content_item = instance.newly_completed_item()
    if content_item is None:
        return

    update_course_progress_on_completion(instance.user, content_item)
    instance.mark_completion_recorded()
