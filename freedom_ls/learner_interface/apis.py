# from ninja import Router, Schema
# from ninja.errors import HttpError
# from typing import List, Optional
# from django.shortcuts import get_object_or_404

# from learner_management.models import Learner
# from content_engine.models import ContentCollection, Topic, Form
# from learner_interface.models import FormProgress, TopicProgress

# from allauth.headless.contrib.ninja.security import x_session_token_auth


# router = Router()


# class CourseRegistrationSchema(Schema):
#     """Schema for a course registration."""

#     id: str
#     title: str
#     slug: str
#     subtitle: Optional[str] = None


# @router.get(
#     "/courses", response=List[CourseRegistrationSchema], auth=[x_session_token_auth]
# )
# def get_learner_courses(request):
#     """
#     Get all courses that the currently logged in learner is registered for.
#     The learner logged in using the allauth login api.
#     """

#     # Get the authenticated user
#     user = request.auth

#     # Check if user is authenticated
#     if not user.is_authenticated:
#         raise HttpError(401, "Authentication required")

#     # Get the learner record for this user
#     try:
#         learner = Learner.objects.get(user=user)
#     except Learner.DoesNotExist:
#         raise HttpError(403, "No learner record found for this user")

#     # Get all registered collections
#     collections = learner.get_course_registrations()

#     # Convert to schema format
#     return [
#         {
#             "id": str(collection.id),
#             "title": collection.title,
#             "slug": collection.slug,
#             "subtitle": collection.subtitle,
#         }
#         for collection in collections
#     ]


# class CourseItemSchema(Schema):
#     """Schema for a single item in a course."""

#     uuid: str
#     slug: str
#     status: str  # "IN_PROGRESS" or "COMPLETE"


# @router.get(
#     "/courses/{slug}/progress",
#     response=List[CourseItemSchema],
#     auth=[x_session_token_auth],
# )
# def get_course_progress(request, slug: str):
#     """
#     Get an ordered list of all the course contents.
#     Returns the same information as views.course_home, but as a data structure.
#     """
#     # Get the authenticated user
#     user = request.auth

#     # Check if user is authenticated
#     if not user.is_authenticated:
#         raise HttpError(401, "Authentication required")

#     # Get the collection
#     collection = get_object_or_404(ContentCollection, slug=slug)

#     # TODO: Check that the learner is registered for the course

#     IN_PROGRESS = "IN_PROGRESS"
#     COMPLETE = "COMPLETE"

#     items = []

#     for child in collection.children():
#         status = None

#         if isinstance(child, Topic):
#             # Check progress
#             topic_progress = TopicProgress.objects.filter(
#                 user=user, topic=child
#             ).first()

#             if topic_progress:
#                 if topic_progress.complete_time:
#                     status = COMPLETE
#                 else:
#                     status = IN_PROGRESS
#                 items.append(
#                     {"uuid": child.pk, "slug": child.slug, "status": child.status}
#                 )

#         elif isinstance(child, Form):
#             # Check progress
#             form_progress = (
#                 FormProgress.objects.filter(user=user, form=child)
#                 .order_by("-start_time")
#                 .first()
#             )

#             if form_progress:
#                 if form_progress.completed_time:
#                     status = COMPLETE
#                 else:
#                     status = IN_PROGRESS
#                 items.append({"uuid": child.pk, "slug": child.slug, "status": status})

#         elif isinstance(child, ContentCollection):
#             TODO

#             # For collections, check if all direct children are complete
#             # TODO: implement proper recursive collection completion checking

#     return items
