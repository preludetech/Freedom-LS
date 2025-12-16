from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from django.contrib.auth import get_user_model

from content_engine.models import Course
from student_management.models import RecommendedCourse

User = get_user_model()


@receiver(post_save, sender=User)
def auto_recommend_courses_for_new_user(sender, instance, created, **kwargs):
    """
    Automatically recommend configured courses when a new user is created.

    Recommendations are created for course slugs listed in the
    AUTOMATICALLY_RECOMMEND_COURSE_SLUGS setting.
    """
    if not created:
        return

    # Get the course slugs to auto-recommend from settings
    course_slugs = getattr(settings, 'AUTOMATICALLY_RECOMMEND_COURSE_SLUGS', [])

    if not course_slugs:
        return

    # Get courses matching the slugs (site-aware filtering happens automatically)
    courses = Course.objects.filter(slug__in=course_slugs)

    # Create recommendations for each course
    for course in courses:
        RecommendedCourse.objects.get_or_create(
            user=instance,
            collection=course,
        )
